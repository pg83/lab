#!/usr/bin/env python3

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'repology' / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lines

SPEC = importlib.util.spec_from_file_location('updater', Path(__file__).with_name('updater.py'))
updater = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = updater
SPEC.loader.exec_module(updater)


class Failure(Exception):
    pass


class FakeNet:
    def __init__(self, tags=None, pages=None, broken=()):
        self.tag_lists = tags or {}
        self.pages = pages or {}
        self.broken = broken

    def tags(self, repo):
        if repo in self.broken:
            raise OSError('unreachable')

        return self.tag_lists[repo]

    def get(self, url):
        return self.pages[url]


class FakeUpdater:
    """Records what Lines asks for; bump moves the holder like the real one."""

    def __init__(self, repo, fail=()):
        self.repo = repo
        self.fail = fail
        self.calls = []

    def bump(self, holder, old, new, packages, literal=False):
        self.calls.append(('bump', holder, old, new, tuple(packages), literal))

        if new in self.fail:
            raise Failure('no checksum')

        path = self.repo / 'pkgs' / holder
        path.write_text(updater.rewrite_version(path.read_text(), old, new, 'f' * 64, literal))

    def render(self, packages, flags=None):
        self.calls.append(('render', tuple(packages)))

    def publish(self, message):
        self.calls.append(('publish', message))

    def restore(self):
        self.calls.append(('restore',))


def write(root, rel, text):
    path = root / 'pkgs' / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)

    return path


def block(version, sha='a' * 64):
    return (
        "{% extends '//die/c/cmake.sh' %}\n\n"
        "{% block version %}\n" + version + "\n{% endblock %}\n\n"
        "{% block fetch %}\nhttps://x/foo-{{self.version().strip()}}.tar.gz\n" + sha + "\n{% endblock %}\n"
    )


CI_HEAD = "{% extends '//die/hub.sh' %}\n\n{% block run_deps %}\n"
CI_TAIL = "{% endblock %}\n"

FOO = lines.Family('foo', 'lib/foo/{0}', '{0}', lines.Tags('foo.git', r'v(\d+\.\d+\.\d+)'), ci=('bin/foo/{0}',))


class FamilyTests(unittest.TestCase):
    def test_lines_and_holders(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write(root, 'lib/foo/1/ix.sh', block('1.0.0'))
            write(root, 'lib/foo/2/t/ix.sh', block('2.1.0'))
            write(root, 'lib/foo/2/ix.sh', "{% extends 't/ix.sh' %}\n")
            write(root, 'lib/foo/t/ix.sh', block('9.9.9'))
            write(root, 'lib/foo/ix.sh', "lib/foo/2\n")
            pkgs = root / 'pkgs'

            self.assertEqual(FOO.lines(pkgs), [(('1',), 'lib/foo/1'), (('2',), 'lib/foo/2')])
            self.assertEqual(FOO.holder(pkgs, 'lib/foo/2'), ('lib/foo/2/t/ix.sh', '2.1.0', False))

    def test_url_holder_when_no_version_block(self):
        fam = lines.Family('llvm', 'lib/llvm/{0}', '{0}', None, url=r'llvmorg-(\d+\.\d+\.\d+)')

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write(root, 'lib/llvm/21/ix.sh', "{% block fetch %}\n{% include 'ver.sh' %}\n{% endblock %}\n")
            write(root, 'lib/llvm/21/ver.sh', 'https://x/llvmorg-21.1.8.tar.gz\n' + 'a' * 64 + '\n')

            self.assertEqual(fam.holder(root / 'pkgs', 'lib/llvm/21'), ('lib/llvm/21/ver.sh', '21.1.8', True))

    def test_keys(self):
        go = lines.Family('go', 'bin/go/lang/{0}', '1.{0}')
        kernel = lines.Family('kernel', 'bin/kernel/{0}/{1}', '{0}.{1}')

        self.assertEqual(go.key_of('1.27.2'), '1.27')
        self.assertEqual(go.args_of('1.28'), ('28',))
        self.assertIsNone(go.args_of('2.0'))
        self.assertEqual(kernel.key_of('7.2.11'), '7.2')
        self.assertEqual(kernel.args_of('7.3'), ('7', '3'))
        self.assertEqual(lines.Family('d', 'bin/dropbear/{0}', '{0}').key_of('2026.94'), '2026')

    def test_owned_by_the_registry(self):
        self.assertTrue(lines.owned(('bin/openssl', 'lib/openssl/3')))
        self.assertTrue(lines.owned(('bin/clang/21/bootstrapped',)))
        self.assertTrue(lines.owned(('lib/python/3/14',)))
        self.assertTrue(lines.owned(('bin/esbuild/21',)))
        self.assertFalse(lines.owned(('lib/zlib',)))
        self.assertFalse(lines.owned(('lib/gtk',)))
        self.assertFalse(lines.owned(('lib/llvmx/1',)))

    def test_stable_filters(self):
        self.assertFalse(lines.below(80)('1.16.92'))
        self.assertTrue(lines.below(80)('1.16.5'))
        self.assertTrue(lines.below(80)('2026.94') is False)
        self.assertTrue(lines.even()('4.24.1'))
        self.assertFalse(lines.even()('4.25.0'))
        self.assertFalse(lines.even()('3.99.5'))


class LinesTests(unittest.TestCase):
    def tree(self, td):
        root = Path(td)
        write(root, 'lib/foo/1/ix.sh', block('1.0.0'))
        write(root, 'lib/foo/2/ix.sh', block('2.0.0', 'b' * 64))
        write(root, 'bin/foo/2/ix.sh', "{% extends '//lib/foo/2/ix.sh' %}\n")
        write(root, lines.CI, CI_HEAD + 'bin/bar\n' + CI_TAIL)

        return root

    def test_patch_updates_stay_inside_their_line(self):
        net = FakeNet({'foo.git': ['v1.0.0', 'v1.0.3', 'v2.0.0', 'v2.1.0', 'v3.0.0', 'v3.0.0-rc1']})

        with tempfile.TemporaryDirectory() as td:
            root = self.tree(td)
            up = FakeUpdater(root)
            lines.Lines(up, net, lambda *a: None, Failure, (FOO,)).run()

            bumps = [c for c in up.calls if c[0] == 'bump']
            self.assertEqual(bumps[0], ('bump', 'lib/foo/1/ix.sh', '1.0.0', '1.0.3', ('lib/foo/1',), False))
            self.assertEqual(bumps[1], ('bump', 'lib/foo/2/ix.sh', '2.0.0', '2.1.0', ('lib/foo/2',), False))
            self.assertIn(('publish', 'up 1.0.0 1.0.3 lib/foo/1'), up.calls)
            self.assertIn(('publish', 'up 2.0.0 2.1.0 lib/foo/2'), up.calls)

    def test_a_new_line_is_cloned_and_joins_ci(self):
        net = FakeNet({'foo.git': ['v2.0.0', 'v3.0.0', 'v3.0.2', 'v4.0.0']})
        fam = lines.Family('foo', 'lib/foo/{0}', '{0}', lines.Tags('foo.git', r'v(\d+\.\d+\.\d+)'),
                           group=('bin/foo/{0}',), ci=('bin/foo/{0}',))

        with tempfile.TemporaryDirectory() as td:
            root = self.tree(td)
            up = FakeUpdater(root)
            lines.Lines(up, net, lambda *a: None, Failure, (fam,)).run()
            pkgs = root / 'pkgs'

            # One new line a run, from the newest one, at the newest release of its prefix.
            self.assertTrue((pkgs / 'lib/foo/3/ix.sh').is_file())
            self.assertFalse((pkgs / 'lib/foo/4').exists())
            self.assertIn('\n3.0.2\n', (pkgs / 'lib/foo/3/ix.sh').read_text())
            self.assertEqual((pkgs / 'bin/foo/3/ix.sh').read_text(), "{% extends '//lib/foo/3/ix.sh' %}\n")
            self.assertIn('bin/foo/3\n', (pkgs / lines.CI).read_text())
            self.assertIn(('render', ('lib/foo/3', 'bin/foo/3')), up.calls)
            self.assertIn(('render', ('set/ci',)), up.calls)
            published = [c[1] for c in up.calls if c[0] == 'publish']
            self.assertEqual(published, ['foo 3: new line 3.0.2 (lib/foo/3, bin/foo/3); CI: bin/foo/3'])

    def test_a_line_outside_its_prefix_is_left_alone(self):
        net = FakeNet({'foo.git': ['v1.0.0', 'v2.0.0', 'v2.0.5']})

        with tempfile.TemporaryDirectory() as td:
            root = self.tree(td)
            write(root, 'lib/foo/1/ix.sh', block('2.0.0'))
            logs = []
            up = FakeUpdater(root)
            lines.Lines(up, net, logs.append, Failure, (FOO,)).run()

            self.assertIn('skip lib/foo/1: holds 2.0.0, outside 1', logs)
            self.assertNotIn(('bump', 'lib/foo/1/ix.sh', '2.0.0', '2.0.5', ('lib/foo/1',), False), up.calls)

    def test_failures_are_logged_and_the_tree_restored(self):
        net = FakeNet({'foo.git': ['v1.0.0', 'v1.0.3', 'v2.0.0']}, broken=('bar.git',))
        bar = lines.Family('bar', 'lib/bar/{0}', '{0}', lines.Tags('bar.git', r'v(.*)'))

        with tempfile.TemporaryDirectory() as td:
            root = self.tree(td)
            logs = []
            up = FakeUpdater(root, fail=('1.0.3',))
            lines.Lines(up, net, logs.append, Failure, (FOO, bar)).run()

            self.assertIn('FAILED lib/foo/1 1.0.0 -> 1.0.3: no checksum', logs)
            self.assertTrue(any(l.startswith('FAILED bar: cannot list versions') for l in logs))
            self.assertEqual(up.calls[-1], ('restore',))
            self.assertIn('lines done: updated=0 failed=2', logs)

    def test_a_new_line_waits_for_what_it_needs(self):
        net = FakeNet({'foo.git': ['v2.0.0', 'v3.0.0']})
        fam = lines.Family('foo', 'lib/foo/{0}', '{0}', lines.Tags('foo.git', r'v(\d+\.\d+\.\d+)'),
                           needs=('lib/llvm/{0}',))

        with tempfile.TemporaryDirectory() as td:
            root = self.tree(td)
            logs = []
            lines.Lines(FakeUpdater(root), net, logs.append, Failure, (fam,)).run()

            self.assertIn('skip foo 3: no lib/llvm/3 yet', logs)
            self.assertFalse((root / 'pkgs/lib/foo/3').exists())


class RetargetTests(unittest.TestCase):
    def test_llvm_names_its_major(self):
        fam = lines.Family('llvm', 'lib/llvm/{0}', '{0}', group=('bin/clang/{0}',), retarget=lines.single)
        text = (
            "{% extends '//lib/llvm/16/ix.sh' %}\n"
            "{% block llvm_major %}\n21\n{% endblock %}\n"
            "{% include '//lib/llvm/21/ver.sh' %}\n"
            "bin/clang/21(c_compiler=bin/clang/21/full,crt_ver=21,libcplpl_ver=21)\n"
        )

        self.assertEqual(lines.retarget_paths(text, fam, ('21',), ('22',)), (
            "{% extends '//lib/llvm/16/ix.sh' %}\n"
            "{% block llvm_major %}\n22\n{% endblock %}\n"
            "{% include '//lib/llvm/22/ver.sh' %}\n"
            "bin/clang/22(c_compiler=bin/clang/22/full,crt_ver=22,libcplpl_ver=22)\n"
        ))

    def test_go_bootstraps_from_the_line_it_came_from(self):
        fam = lines.FAMILIES[[f.name for f in lines.FAMILIES].index('go')]
        text = "{% extends '//bin/go/lang/22/ix.sh' %}\n{% block go_bootstrap %}\nbin/go/lang/26\n{% endblock %}\n"

        self.assertEqual(
            lines.retarget_paths(text, fam, ('27',), ('28',)),
            "{% extends '//bin/go/lang/22/ix.sh' %}\n{% block go_bootstrap %}\nbin/go/lang/27\n{% endblock %}\n",
        )

    def test_kernel_tree_follows_the_major(self):
        fam = lines.FAMILIES[[f.name for f in lines.FAMILIES].index('kernel')]
        text = 'https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-{{self.kernel_version().strip()}}.tar.xz\n'

        self.assertIn('/v8.x/', lines.retarget_paths(text, fam, ('7', '2'), ('8', '0')))
        self.assertIn('/v7.x/', lines.retarget_paths(text, fam, ('7', '2'), ('7', '3')))

    def test_a_dotted_key_follows_but_not_inside_a_version(self):
        fam = lines.Family('python', 'lib/python/3/{0}', '3.{0}', group=('bin/python/{0}',))
        text = (
            "cd ${out}/lib/python3.14\nlibpython3.14.a\n{% block version %}\n3.14.8\n{% endblock %}\n"
            "bin/python/14 lib/python/3/14 3.140 13.14\nboost_3_14 ok\n"
        )

        self.assertEqual(lines.retarget_paths(text, fam, ('14',), ('15',)), (
            "cd ${out}/lib/python3.15\nlibpython3.15.a\n{% block version %}\n3.14.8\n{% endblock %}\n"
            "bin/python/15 lib/python/3/15 3.140 13.14\nboost_3_15 ok\n"
        ))

    def test_a_new_line_adopts_what_waited_for_it(self):
        fam = lines.Family('spirv', 'lib/spirv/{0}', '{0}', group=('bin/llvm/spirv/{0}',), adopt=('lib/clc/{0}',))

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = write(root, 'lib/clc/22/ix.sh', 'bin/llvm/spirv/21\nlib/llvm/22\n')
            write(root, 'lib/clc/21/ix.sh', 'bin/llvm/spirv/21\n')

            self.assertEqual(lines.adopt(root / 'pkgs', fam, ('21',), ('22',)), ['lib/clc/22/ix.sh'])
            self.assertEqual(path.read_text(), 'bin/llvm/spirv/22\nlib/llvm/22\n')
            self.assertEqual((root / 'pkgs/lib/clc/21/ix.sh').read_text(), 'bin/llvm/spirv/21\n')

    def test_ci_mirrors_what_it_built_of_the_old_line(self):
        fam = lines.Family('llvm', 'lib/llvm/{0}', '{0}', group=('bin/clang/{0}',), ci=('bin/clang/{0}',),
                           retarget=lines.single)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write(root, lines.CI, CI_HEAD + 'bin/clang/20\nbin/clang/21/bootstrapped\nbin/clang/210x\n' + CI_TAIL)

            self.assertEqual(lines.add_to_ci(root / 'pkgs', fam, ('21',), ('22',)), ['bin/clang/22/bootstrapped'])
            self.assertEqual(
                (root / 'pkgs' / lines.CI).read_text(),
                CI_HEAD + 'bin/clang/20\nbin/clang/21/bootstrapped\nbin/clang/22/bootstrapped\nbin/clang/210x\n' + CI_TAIL,
            )

            write(root, lines.CI, CI_HEAD + 'bin/bar\n' + CI_TAIL)
            self.assertEqual(lines.add_to_ci(root / 'pkgs', fam, ('21',), ('22',)), ['bin/clang/22'])
            self.assertEqual((root / 'pkgs' / lines.CI).read_text(), CI_HEAD + 'bin/bar\nbin/clang/22\n' + CI_TAIL)


class BumpTests(unittest.TestCase):
    probe = '0' * 64

    def test_bump_probes_a_version_block(self):
        actual = 'f' * 64
        builder = mock.Mock()
        builder.build.return_value = updater.BuildResult(
            2, b'molot exec: predict mismatch: /x expected=' + self.probe.encode() + b' actual=' + actual.encode(),
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = write(root, 'bin/gdb/17/ix.sh', block('17.1'))
            worker = updater.PackageUpdater(root, builder, env={})
            worker.show_diff = lambda: None

            with mock.patch.object(updater.secrets, 'token_hex', return_value=self.probe):
                worker.bump('bin/gdb/17/ix.sh', '17.1', '17.2', ['bin/gdb/17'])

            self.assertIn('\n17.2\n', path.read_text())
            self.assertIn(actual, path.read_text())
            builder.build.assert_called_once_with(['bin/gdb/17'])

    def test_bump_rewrites_a_literal_url(self):
        actual = 'f' * 64
        builder = mock.Mock()
        builder.build.return_value = updater.BuildResult(
            2, b'molot exec: predict mismatch: /x expected=' + self.probe.encode() + b' actual=' + actual.encode(),
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = write(root, 'lib/llvm/21/ver.sh', 'https://x/llvmorg-21.1.8.tar.gz\n' + 'a' * 64 + '\n')
            write(root, 'lib/llvm/21/ix.sh', '')
            worker = updater.PackageUpdater(root, builder, env={})
            worker.show_diff = lambda: None

            with mock.patch.object(updater.secrets, 'token_hex', return_value=self.probe):
                worker.bump('lib/llvm/21/ver.sh', '21.1.8', '21.1.9', ['lib/llvm/21'], literal=True)

            self.assertEqual(path.read_text(), 'https://x/llvmorg-21.1.9.tar.gz\n' + actual + '\n')

    def test_failed_bump_leaves_the_recipe(self):
        builder = mock.Mock()
        builder.build.return_value = updater.BuildResult(1, b'boom')

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            original = block('17.1')
            path = write(root, 'bin/gdb/17/ix.sh', original)
            worker = updater.PackageUpdater(root, builder, env={})
            worker.show_diff = lambda: None

            with self.assertRaises(updater.CandidateFailure):
                worker.bump('bin/gdb/17/ix.sh', '17.1', '17.2', ['bin/gdb/17'])

            self.assertEqual(path.read_text(), original)

    def test_go_latest_is_the_newest_line_of_the_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            for n in ('4', '26', '28', 't'):
                (root / 'pkgs/bin/go/lang' / n).mkdir(parents=True)

            self.assertEqual(updater.go_latest(root), 28)


if __name__ == '__main__':
    unittest.main()
