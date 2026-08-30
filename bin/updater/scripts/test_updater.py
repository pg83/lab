#!/usr/bin/env python3

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SPEC = importlib.util.spec_from_file_location('updater', Path(__file__).with_name('updater.py'))
updater = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = updater
SPEC.loader.exec_module(updater)


class FakeBuilder:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def build(self, packages):
        self.calls.append(list(packages))
        return self.results.pop(0)


class FakePackageUpdater(updater.PackageUpdater):
    def __init__(self, repo, builder):
        super().__init__(repo, builder, env={})
        self.commits = []

    def dependency_files(self, packages):
        return ['bin/foo/ix.sh']

    def show_diff(self):
        pass

    def commit_and_push(self, candidate):
        self.commits.append(candidate)


class UpdaterTests(unittest.TestCase):
    probe = '0' * 64

    def test_publish_rebases_before_push_for_parallel_fixer(self):
        worker = updater.PackageUpdater(Path('/work/ix'), None, branch='main', env={})
        candidate = updater.Candidate('1.0', '2.0', ('bin/foo',))

        def git_result(*args, **kwargs):
            return mock.Mock(returncode=1 if args[:3] == ('diff', '--cached', '--quiet') else 0)

        with mock.patch.object(worker, 'git', side_effect=git_result) as git, \
             mock.patch.object(worker, 'regenerate_repology_stats') as regenerate:
            worker.commit_and_push(candidate)

        commands = [call.args for call in git.call_args_list]
        stats_add = ('add', '--', updater.REPOLOGY_STATS_PATH)
        amend = ('commit', '--amend', '--no-edit')
        self.assertLess(commands.index(('fetch', 'origin', 'main')),
                        commands.index(('rebase', 'origin/main')))
        self.assertLess(commands.index(('rebase', 'origin/main')),
                        commands.index(stats_add))
        self.assertLess(commands.index(stats_add), commands.index(amend))
        self.assertLess(commands.index(amend),
                        commands.index(('push', 'origin', 'HEAD:refs/heads/main')))
        regenerate.assert_called_once_with()

    def test_publish_rebuilds_stats_after_push_race(self):
        worker = updater.PackageUpdater(Path('/work/ix'), None, branch='main', env={})
        candidate = updater.Candidate('1.0', '2.0', ('bin/foo',))
        pushes = 0

        def git_result(*args, **kwargs):
            nonlocal pushes

            if args[:3] == ('diff', '--cached', '--quiet'):
                return mock.Mock(returncode=1)

            if args and args[0] == 'push':
                pushes += 1
                return mock.Mock(returncode=1 if pushes == 1 else 0)

            return mock.Mock(returncode=0)

        with mock.patch.object(worker, 'git', side_effect=git_result) as git, \
             mock.patch.object(worker, 'regenerate_repology_stats') as regenerate:
            worker.commit_and_push(candidate)

        commands = [call.args for call in git.call_args_list]
        self.assertEqual(regenerate.call_count, 2)
        self.assertIn(
            (
                'restore', '--source=HEAD^', '--staged', '--worktree',
                '--', updater.REPOLOGY_STATS_PATH,
            ),
            commands,
        )
        self.assertEqual(
            commands.count(('push', 'origin', 'HEAD:refs/heads/main')),
            2,
        )

    def test_restore_returns_to_run_source_revision(self):
        worker = updater.PackageUpdater(
            Path('/work/ix'),
            None,
            branch='main',
            source_revision='0123456789abcdef',
            env={},
        )

        with mock.patch.object(worker, 'git') as git:
            worker.restore()

        self.assertEqual(
            [call.args for call in git.call_args_list],
            [
                ('restore', '--source=HEAD', '--staged', '--worktree', '--', '.'),
                ('switch', '--detach', '0123456789abcdef'),
            ],
        )

    def test_repology_stats_use_complete_repository_export(self):
        worker = updater.PackageUpdater(Path('/work/ix'), None, env={'X': '1'})

        with mock.patch.object(updater.subprocess, 'run') as run:
            worker.regenerate_repology_stats()

        run.assert_called_once_with(
            ('ix_repo_export',),
            cwd=Path('/work/ix'),
            env={'X': '1'},
            check=True,
        )

    def test_repology_filter_keeps_original_skip_semantics(self):
        data = {
            'zlib': [
                {'repo': 'stalix', 'version': '1.2', 'srcname': 'lib/zlib'},
                {'status': 'newest', 'version': '1.3'},
            ],
            'python': [
                {'repo': 'stalix', 'version': '3.13', 'srcname': 'bin/python'},
                {'status': 'newest', 'version': '3.14'},
            ],
            'unclassified/foo': [
                {'repo': 'stalix', 'version': '1', 'srcname': 'bin/foo'},
                {'status': 'newest', 'version': '2'},
            ],
        }

        self.assertEqual(
            list(updater.candidates_from_repology(data)),
            [updater.Candidate('1.2', '1.3', ('lib/zlib',))],
        )

    def test_repology_fetches_every_page(self):
        first = {f'p{number:03d}': [number] for number in range(200)}
        second = {'p199': [199], 'p200': [200]}
        url = 'https://repology.example/api/v1/projects/?inrepo=stalix_dev&outdated=1'

        with mock.patch.object(
            updater, 'fetch_repology_page', side_effect=(first, second),
        ) as fetch:
            data = updater.fetch_repology(url)

        self.assertEqual(len(data), 201)
        self.assertEqual(data['p200'], [200])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(
            fetch.call_args_list[1].args[0],
            'https://repology.example/api/v1/projects/p199/?inrepo=stalix_dev&outdated=1',
        )

    def test_prepare_recipe_keeps_go_upgrade_rule(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'ix.sh'
            path.write_text(
                "{% block version %}\n1.0\n{% endblock %}\n"
                "{% block go_url %}https://x/v1.0.tar.gz{% endblock %}\n"
                "{% block go_sha %}\n" + 'a' * 64 + "\n{% endblock %}\n"
                "{% block go_tool %}bin/go/lang/23{% endblock %}\n"
            )

            self.assertTrue(updater.prepare_recipe(path, '1.0', '2.0', self.probe))
            data = path.read_text()
            self.assertIn('2.0', data)
            self.assertIn(self.probe, data)
            self.assertIn('bin/go/lang/26', data)
            self.assertIn('{% block go_tool %}', data)

    def test_prepare_recipe_uses_current_cargo_toolchain(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'ix.sh'
            path.write_text(
                "{% block version %}\n1.0\n{% endblock %}\n"
                "{% block cargo_url %}https://x/v1.0.tar.gz{% endblock %}\n"
                "{% block cargo_sha %}\n" + 'a' * 64 + "\n{% endblock %}\n"
                "{% block cargo_tool %}bld/cargo/91{% endblock %}\n"
                "{% block bld_tool %}bld/rust/91{% endblock %}\n"
            )

            self.assertTrue(updater.prepare_recipe(path, '1.0', '2.0', self.probe))
            data = path.read_text()
            self.assertIn('bld/cargo/96', data)
            self.assertIn('bld/rust/96', data)
            self.assertNotIn('bld/cargo/91', data)
            self.assertNotIn('bld/rust/91', data)

    def test_prepare_recipe_matches_complete_version_line(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'ix.sh'
            original = (
                "{% block version %}\n1.9.4\n{% endblock %}\n"
                "{% block fetch %}\nhttps://x/v{{self.version().strip()}}.tar.gz\n" +
                'a' * 64 + "\n{% endblock %}\n"
            )
            path.write_text(original)

            self.assertFalse(updater.prepare_recipe(path, '1.9', '1.9.4', self.probe))
            self.assertEqual(path.read_text(), original)

    def test_prepare_recipe_moves_attr_from_cgit_snapshot_to_release(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'ix.sh'
            path.write_text(
                "{% block version %}\n2.5.2\n{% endblock %}\n"
                "{% block fetch %}\n" + updater.ATTR_SNAPSHOT_URL + "\n" +
                'a' * 64 + "\n{% endblock %}\n"
            )

            self.assertTrue(updater.prepare_recipe(path, '2.5.2', '2.6.0', self.probe))
            data = path.read_text()
            self.assertIn(updater.ATTR_RELEASE_URL, data)
            self.assertNotIn(updater.ATTR_SNAPSHOT_URL, data)
            self.assertIn(self.probe, data)

    def test_noauto_recipe_is_not_changed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'ix.sh'
            original = 'noauto\n1.0\n' + 'a' * 64 + '\n'
            path.write_text(original)

            self.assertFalse(updater.prepare_recipe(path, '1.0', '2.0', self.probe))
            self.assertEqual(path.read_text(), original)

    def test_redirect_and_unwrap_rules_match_ix_upver(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            recipe = repo / 'pkgs/bin/foo/ix.sh'
            recipe.parent.mkdir(parents=True)
            recipe.write_text('# check set/ci/tier/0 bin/foo/base\n')

            self.assertEqual(
                list(updater.packages_to_build(repo, ('bin/foo/unwrap',))),
                ['set/ci/tier/0', 'bin/foo/base'],
            )

    def test_extracts_molot_predict_sha_not_a_task_guid(self):
        actual = 'b' * 64
        unrelated = 'c' * 64
        output = (
            unrelated.encode() + b' task-guid\n' +
            b'molot exec: predict mismatch: predict mismatch: /x '
            b'expected=' + self.probe.encode() + b' actual=' + actual.encode() + b'\n' +
            unrelated.encode() + b' later-noise\n'
        )

        self.assertEqual(updater.extract_reported_sha(output, self.probe), actual)

    def test_extracts_colored_direct_fetch_checksum(self):
        actual = 'e' * 64
        output = (
            b'got \x1b[91m' + actual.encode() + b'\x1b[0m checksum, not ' +
            self.probe.encode()
        )

        self.assertEqual(updater.extract_reported_sha(output, self.probe), actual)

    def test_pzd_checksum_is_bound_to_this_attempts_probe(self):
        tarball = 'a' * 64
        pzd = 'b' * 64
        stale_pzd = 'c' * 64

        for filename in (
            'go_v3_' + self.probe + '.pzd',
            'cargo_v4_' + self.probe + '.pzd',
            'git_v3_src_' + self.probe + '.pzd',
        ):
            with self.subTest(filename=filename):
                output = (
                    tarball.encode() + b'  /tmp/source.tar.gz\n' +
                    pzd.encode() + b'  /tmp/' + filename.encode() + b'\n' +
                    stale_pzd.encode() + b'  /tmp/go_v3_' +
                    ('1' * 64).encode() + b'.pzd\n'
                )

                self.assertEqual(
                    updater.extract_reported_sha(output, self.probe),
                    pzd,
                )

    def test_success_is_two_builds_then_commit_without_final_build(self):
        actual = 'd' * 64
        checksum_output = (
            b'molot exec: predict mismatch: predict mismatch: /x expected=' +
            self.probe.encode() + b' actual=' + actual.encode()
        )
        builder = FakeBuilder([
            updater.BuildResult(0, b'ok'),
            updater.BuildResult(2, checksum_output),
        ])

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            recipe = repo / 'pkgs/bin/foo/ix.sh'
            recipe.parent.mkdir(parents=True)
            recipe.write_text(
                "{% block version %}\n1.0\n{% endblock %}\n"
                "{% block fetch %}\nhttps://x/foo-1.0.tar.gz\n" + 'a' * 64 + "\n{% endblock %}\n"
            )
            worker = FakePackageUpdater(repo, builder)
            candidate = updater.Candidate('1.0', '2.0', ('bin/foo',))

            with mock.patch.object(updater.secrets, 'token_hex', return_value=self.probe):
                self.assertTrue(worker.process(candidate))
            self.assertEqual(builder.calls, [['bin/foo'], ['bin/foo']])
            self.assertEqual(worker.commits, [candidate])
            self.assertIn(actual, recipe.read_text())
            self.assertNotIn(self.probe, recipe.read_text())

    def test_failed_preflight_does_not_touch_recipe(self):
        builder = FakeBuilder([
            updater.BuildResult(2, b'node failed: bin/foo'),
        ])

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            recipe = repo / 'pkgs/bin/foo/ix.sh'
            recipe.parent.mkdir(parents=True)
            original = (
                "{% block version %}\n1.0\n{% endblock %}\n"
                "{% block fetch %}\nhttps://x/foo-1.0.tar.gz\n" + 'a' * 64 + "\n{% endblock %}\n"
            )
            recipe.write_text(original)
            worker = FakePackageUpdater(repo, builder)

            with self.assertRaises(updater.CandidateFailure):
                worker.process(updater.Candidate('1.0', '2.0', ('bin/foo',)))

            self.assertEqual(recipe.read_text(), original)
            self.assertEqual(worker.commits, [])

    def test_process_ignores_non_file_dependency_entries(self):
        actual = 'f' * 64
        checksum_output = (
            b'molot exec: predict mismatch: predict mismatch: /x expected=' +
            self.probe.encode() + b' actual=' + actual.encode()
        )
        builder = FakeBuilder([
            updater.BuildResult(0, b'ok'),
            updater.BuildResult(2, checksum_output),
        ])

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            recipe = repo / 'pkgs/bin/foo/ix.sh'
            recipe.parent.mkdir(parents=True)
            recipe.write_text(
                "{% block version %}\n1.0\n{% endblock %}\n"
                "{% block fetch %}\nhttps://x/foo.tar.gz\n" +
                'a' * 64 + "\n{% endblock %}\n"
            )
            source = recipe.parent / 'build.rs'
            source.write_text('fn main() {}\n')
            worker = FakePackageUpdater(repo, builder)
            worker.dependency_files = lambda packages: [
                'bin/foo/ix.sh',
                'bin/foo/build.rs/base64',
            ]

            with mock.patch.object(updater.secrets, 'token_hex', return_value=self.probe):
                self.assertTrue(worker.process(
                    updater.Candidate('1.0', '2.0', ('bin/foo',)),
                ))
            self.assertIn(actual, recipe.read_text())

    def test_go_update_installs_pzd_not_tarball_checksum(self):
        tarball = 'a' * 64
        pzd = 'b' * 64
        checksum_output = (
            pzd.encode() + b'  /tmp/go_v3_' + self.probe.encode() + b'.pzd\n' +
            tarball.encode() + b'  /tmp/source.tar.gz\n'
        )
        builder = FakeBuilder([
            updater.BuildResult(0, b'ok'),
            updater.BuildResult(2, checksum_output),
        ])

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            recipe = repo / 'pkgs/bin/foo/ix.sh'
            recipe.parent.mkdir(parents=True)
            recipe.write_text(
                "{% block version %}\n1.0\n{% endblock %}\n"
                "{% block go_url %}\nhttps://x/foo.tar.gz\n{% endblock %}\n"
                "{% block go_sha %}\n" + 'c' * 64 + "\n{% endblock %}\n"
            )
            worker = FakePackageUpdater(repo, builder)

            with mock.patch.object(updater.secrets, 'token_hex', return_value=self.probe):
                self.assertTrue(worker.process(
                    updater.Candidate('1.0', '2.0', ('bin/foo',)),
                ))
            self.assertIn(pzd, recipe.read_text())
            self.assertNotIn(tarball, recipe.read_text())


if __name__ == '__main__':
    unittest.main()
