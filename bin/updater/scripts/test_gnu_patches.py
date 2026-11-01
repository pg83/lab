import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'repology' / 'scripts'))

import gnu_patches as gnu
import lines
import updater


def recipe(series, version, level=0):
    base, _ = gnu.parse(version)
    fetch = [series.base_url(base), 'a' * 64]

    for n in range(1, level + 1):
        fetch += [series.patch_url(base, n), f'{n:064x}']

    return (
        gnu.MARKER + '\n'
        '{% block version %}\n' + version + '\n{% endblock %}\n'
        '{% block fetch %}\n' + '\n'.join(fetch) + '\n{% endblock %}\n'
        '{% block unpack %}\napply GNU patches\n{% endblock %}\n'
    )


def patch(series, base, level):
    name = series.patch_url(base, level).rsplit('/', 1)[1]
    return f'{series.name.title()}-Release: {base}\nPatch-ID:\t{name}\n'.encode() + b'patch bytes\xff\n'


class GnuPatchTests(unittest.TestCase):
    def test_patch_versions_are_newer_than_the_base_and_older_patchlevels(self):
        records = [{'status': 'newest', 'version': '5.3p20'},
                   {'status': 'newest', 'version': '5.3.p20'}]
        self.assertEqual(set(updater.newest_versions(records, '5.3')), {'5.3p20', '5.3.p20'})
        self.assertEqual(set(updater.newest_versions(records, '5.3p19')), {'5.3p20', '5.3.p20'})
        self.assertEqual(updater.newest_versions(records, '5.3p20'), ())
        self.assertEqual(updater.newest_versions([{'status': 'newest', 'version': '8.3p6'}], '8.3'), ('8.3p6',))

    def test_readline_keeps_existing_pins_and_fetches_every_missing_patch(self):
        series = gnu.SERIES[1]
        blobs = {series.patch_url('8.3', n): patch(series, '8.3', n) for n in range(4, 7)}
        net = mock.Mock()
        net.get.side_effect = lambda url, binary: blobs[url]
        original = recipe(series, '8.3', 3)
        updated = gnu.rewrite(original, series, '8.3.p6', net)
        self.assertEqual(gnu.content(updated, 'version'), '8.3p6')
        self.assertEqual(len(gnu.pins(updated)), 7)
        self.assertEqual(gnu.pins(updated)[series.patch_url('8.3', 3)], f'{3:064x}')
        self.assertEqual(gnu.pins(updated)[series.patch_url('8.3', 4)], hashlib.sha256(blobs[series.patch_url('8.3', 4)]).hexdigest())
        self.assertEqual(net.get.call_args_list, [mock.call(url, binary=True) for url in blobs])
        self.assertEqual(gnu.content(updated, 'unpack'), gnu.content(original, 'unpack'))

    def test_new_base_discards_previous_patch_series(self):
        series = gnu.SERIES[0]
        net = mock.Mock()
        net.get.return_value = b'new base archive'
        updated = gnu.rewrite(recipe(series, '5.3p20', 20), series, '5.4', net)
        self.assertEqual(gnu.content(updated, 'version'), '5.4')
        self.assertNotIn('5.3', updated)
        self.assertNotIn('bash53-', updated)
        self.assertEqual(gnu.pins(updated), {series.base_url('5.4'): hashlib.sha256(b'new base archive').hexdigest()})
        net.get.assert_called_once_with(series.base_url('5.4'), binary=True)

    def test_rejects_html_wrong_release_and_wrong_patch_number(self):
        series = gnu.SERIES[0]

        for payload in (b'<html>mirror error</html>', patch(series, '5.2', 1), patch(series, '5.3', 2)):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                gnu.rewrite(recipe(series, '5.3'), series, '5.3p1', mock.Mock(get=mock.Mock(return_value=payload)))

    def test_missing_patch_does_not_skip_a_number(self):
        series = gnu.SERIES[0]
        net = mock.Mock()
        net.get.side_effect = [patch(series, '5.3', 1), lines.NetFailure('404')]

        with self.assertRaises(lines.NetFailure):
            gnu.rewrite(recipe(series, '5.3'), series, '5.3p3', net)

        self.assertEqual(net.get.call_args_list, [mock.call(series.patch_url('5.3', n), binary=True) for n in (1, 2)])

    def test_explicit_hold_is_respected(self):
        series = gnu.SERIES[1]

        with self.assertRaises(ValueError):
            gnu.rewrite(recipe(series, '8.3') + '# noauto\n', series, '8.3p6', mock.Mock())

    def test_base_release_listing_never_downgrades_patched_bash(self):
        family = next(f for f in lines.FAMILIES if f.name == 'bash')
        self.assertIsNone(lines.newest(['5.3'], '5', family, '5.3p20'))
        self.assertEqual(lines.newest(['5.3', '5.4'], '5', family, '5.3p20'), '5.4')

    def test_generic_dependency_rewrite_leaves_gnu_recipes_alone(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'ix.sh'
            original = recipe(gnu.SERIES[1], '8.3p6', 6)
            path.write_text(original)
            self.assertFalse(updater.recipe_accepts_update(path, '8.3p6'))
            self.assertFalse(updater.prepare_recipe(path, '8.3p6', '8.4', '0' * 64))
            self.assertEqual(path.read_text(), original)

    def test_line_bump_resets_patches_for_a_new_bash_major(self):
        series = gnu.owner(['bin/bash/6'])

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'pkgs' / series.holder
            path.parent.mkdir(parents=True)
            # A new line is copied from the old line before bump() runs.
            path.write_text(recipe(series, '5.3p20', 20))
            (path.parent.parent / 'ix.sh').write_text('extends t/ix.sh\n')
            builder = mock.Mock()
            worker = updater.PackageUpdater(root, builder, env={})

            with mock.patch.object(lines.Net, 'get', return_value=b'new archive') as get, \
                 mock.patch.object(worker, 'render'), \
                 mock.patch.object(worker, 'show_diff'):
                worker.bump(series.holder, '5.3p20', '6.0', ['bin/bash/6'])

            self.assertEqual(gnu.content(path.read_text(), 'version'), '6.0')
            self.assertNotIn('bash53-', path.read_text())
            get.assert_called_once_with(series.base_url('6.0'), binary=True)
            builder.build.assert_not_called()

    def test_process_uses_current_recipe_and_skips_stale_repology(self):
        series = gnu.SERIES[1]

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'pkgs' / series.holder
            path.parent.mkdir(parents=True)
            path.write_text(recipe(series, '8.3p6', 6))
            builder = mock.Mock()
            worker = updater.PackageUpdater(root, builder, env={})
            self.assertFalse(worker.process(updater.Candidate('8.3', '8.3p6', ('lib/readline',))))
            builder.build.assert_not_called()

    def test_process_publishes_full_patchlevel_after_base_build(self):
        series = gnu.SERIES[1]

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / 'pkgs' / series.holder
            path.parent.mkdir(parents=True)
            path.write_text(recipe(series, '8.3p5', 5))
            builder = mock.Mock()
            builder.build.return_value = updater.BuildResult(0, b'green')
            worker = updater.PackageUpdater(root, builder, env={})

            with mock.patch.object(lines.Net, 'get', return_value=patch(series, '8.3', 6)), \
                 mock.patch.object(worker, 'render') as render, \
                 mock.patch.object(worker, 'show_diff'), \
                 mock.patch.object(worker, 'commit_and_push') as publish:
                self.assertTrue(worker.process(updater.Candidate('8.3', '8.3.p6', ('lib/readline',))))

            self.assertEqual(gnu.content(path.read_text(), 'version'), '8.3p6')
            builder.build.assert_called_once_with(['lib/readline'])
            render.assert_called_once_with(['lib/readline'])
            publish.assert_called_once_with(updater.Candidate('8.3p5', '8.3p6', ('lib/readline',)))

    def test_net_preserves_non_utf8_patch_bytes(self):
        net = lines.Net({}, attempts=1)

        with mock.patch.object(lines.subprocess, 'run', return_value=mock.Mock(returncode=0, stdout=b'\xff\n')):
            self.assertEqual(net.get('https://ftp.gnu.org/patch', binary=True), b'\xff\n')


if __name__ == '__main__':
    unittest.main()
