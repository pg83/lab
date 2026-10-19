#!/usr/bin/env python3

import importlib.util
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'repology' / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import groups

SPEC = importlib.util.spec_from_file_location('updater', Path(__file__).with_name('updater.py'))
updater = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = updater
SPEC.loader.exec_module(updater)


def write(root, rel, text):
    path = root / 'pkgs' / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)

    return path


def block(version, url='https://x/{{self.version().strip()}}.tar.gz', sha='a' * 64):
    return "{% block version %}\n" + version + "\n{% endblock %}\n{% block fetch %}\n" + url + "\n" + sha + "\n{% endblock %}\n"


class FakeNet:
    def __init__(self, tags):
        self.tag_lists = tags

    def tags(self, repo):
        return self.tag_lists[repo]


class FakeBuilder:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def build(self, packages, keep_going=False):
        self.calls.append((list(packages), keep_going))

        return updater.BuildResult(2, self.outputs.pop(0))


class Recorder(updater.PackageUpdater):
    def __init__(self, repo, builder):
        super().__init__(repo, builder, env={})
        self.calls = []

    def show_diff(self):
        pass

    def render(self, packages, flags=None):
        self.calls.append(('render', tuple(packages)))

    def publish(self, message):
        self.calls.append(('publish', message))

    def restore(self):
        self.calls.append(('restore',))


def mismatch(probe, actual):
    return b'molot exec: predict mismatch: /x expected=' + probe.encode() + b' actual=' + actual.encode() + b'\n'


SDK = groups.Group('sdk', r'\d+\.\d+\.\d+\.\d+', (
    groups.Member('lib/a', 'lib/a/ix.sh', 'a.git', 'vulkan-sdk-{}'),
    groups.Member('lib/b', 'lib/b/t/ix.sh', 'b.git', 'vulkan-sdk-{}'),
    groups.Member('lib/h', 'lib/h/ver.sh', 'h.git', 'vulkan-sdk-{}', literal=True),
))


class GroupTests(unittest.TestCase):
    def tree(self, td, a='1.4.357.0', b='1.4.321.0', h='1.4.357.0'):
        root = Path(td)
        write(root, 'lib/a/ix.sh', block(a))
        write(root, 'lib/b/ix.sh', "{% extends 't/ix.sh' %}\n")
        write(root, 'lib/b/t/ix.sh', block(b, sha='b' * 64))
        write(root, 'lib/h/ix.sh', "{% block fetch %}\n{% include 'ver.sh' %}\n{% endblock %}\n")
        write(root, 'lib/h/ver.sh', f'https://x/archive/refs/tags/vulkan-sdk-{h}.tar.gz\n' + 'c' * 64 + '\n')

        return root

    def test_release_is_what_every_member_tagged(self):
        net = FakeNet({
            'a.git': ['vulkan-sdk-1.4.357.0', 'vulkan-sdk-1.4.363.0', 'vulkan-sdk-1.4.370.0', 'v1.4.370'],
            'b.git': ['vulkan-sdk-1.4.357.0', 'vulkan-sdk-1.4.363.0', 'vulkan-sdk-1.4.370.0'],
            'h.git': ['vulkan-sdk-1.4.357.0', 'vulkan-sdk-1.4.363.0', 'sdk-1.4.370.0'],
        })
        probes = iter(['1' * 64, '2' * 64, '3' * 64])
        builder = FakeBuilder([mismatch('1' * 64, 'd' * 64) + mismatch('3' * 64, 'f' * 64), mismatch('2' * 64, 'e' * 64)])
        logs = []

        with tempfile.TemporaryDirectory() as td:
            root = self.tree(td)
            worker = Recorder(root, builder)

            with unittest.mock.patch.object(updater.secrets, 'token_hex', side_effect=lambda n: next(probes)):
                groups.Groups(worker, net, logs.append, updater.CandidateFailure, (SDK,)).run()

            self.assertIn('sdk 1.4.370.0: not released by lib/h yet', logs)
            self.assertEqual(builder.calls, [(['lib/a', 'lib/b', 'lib/h'], True)] * 2)
            self.assertIn('\n1.4.363.0\n', (root / 'pkgs/lib/a/ix.sh').read_text())
            self.assertIn('d' * 64, (root / 'pkgs/lib/a/ix.sh').read_text())
            self.assertIn('\n1.4.363.0\n', (root / 'pkgs/lib/b/t/ix.sh').read_text())
            self.assertIn('e' * 64, (root / 'pkgs/lib/b/t/ix.sh').read_text())
            self.assertEqual(
                (root / 'pkgs/lib/h/ver.sh').read_text(),
                'https://x/archive/refs/tags/vulkan-sdk-1.4.363.0.tar.gz\n' + 'f' * 64 + '\n',
            )
            self.assertIn(('render', ('set/ci',)), worker.calls)
            self.assertIn(('publish', 'sdk 1.4.363.0: lib/a 1.4.357.0, lib/b 1.4.321.0, lib/h 1.4.357.0'), worker.calls)
            self.assertIn('groups done: updated=1 failed=0', logs)

    def test_only_members_behind_move(self):
        net = FakeNet({r: ['vulkan-sdk-1.4.357.0'] for r in ('a.git', 'b.git', 'h.git')})
        builder = FakeBuilder([mismatch('1' * 64, 'e' * 64)])
        logs = []

        with tempfile.TemporaryDirectory() as td:
            root = self.tree(td)
            worker = Recorder(root, builder)

            with unittest.mock.patch.object(updater.secrets, 'token_hex', return_value='1' * 64):
                groups.Groups(worker, net, logs.append, updater.CandidateFailure, (SDK,)).run()

            self.assertEqual(builder.calls, [(['lib/b'], True)])
            self.assertIn(('publish', 'sdk 1.4.357.0: lib/b 1.4.321.0'), worker.calls)

    def test_a_member_without_a_checksum_holds_the_whole_group(self):
        net = FakeNet({r: ['vulkan-sdk-1.4.363.0'] for r in ('a.git', 'b.git', 'h.git')})
        probes = iter(['1' * 64, '2' * 64, '3' * 64])
        builder = FakeBuilder([mismatch('1' * 64, 'd' * 64), b'boom'])
        logs = []

        with tempfile.TemporaryDirectory() as td:
            root = self.tree(td)
            before = {p: p.read_text() for p in (root / 'pkgs').rglob('*.sh')}
            worker = Recorder(root, builder)

            with unittest.mock.patch.object(updater.secrets, 'token_hex', side_effect=lambda n: next(probes)):
                groups.Groups(worker, net, logs.append, updater.CandidateFailure, (SDK,)).run()

            self.assertEqual({p: p.read_text() for p in before}, before)
            self.assertFalse(any(c[0] == 'publish' for c in worker.calls))
            self.assertTrue(any(l.startswith('FAILED sdk: build output contains no checksum for lib/') for l in logs))

    def test_up_to_date_does_nothing(self):
        net = FakeNet({r: ['vulkan-sdk-1.4.357.0', 'vulkan-sdk-1.4.321.0'] for r in ('a.git', 'b.git', 'h.git')})

        with tempfile.TemporaryDirectory() as td:
            root = self.tree(td, b='1.4.357.0')
            worker = Recorder(root, FakeBuilder([]))
            groups.Groups(worker, net, lambda *a: None, updater.CandidateFailure, (SDK,)).run()

            self.assertEqual(worker.calls, [('restore',)])

    def test_registry(self):
        self.assertTrue(groups.owned(('lib/qt/6/base/nogui',)))
        self.assertTrue(groups.owned(('bin/vulkan/tools/cube', 'bin/vulkan/tools/info')))
        self.assertTrue(groups.owned(('lib/spirv/headers',)))
        self.assertFalse(groups.owned(('lib/qt/keychain', 'lib/glslang', 'lib/shaderc')))
        qt = groups.GROUPS[0]
        self.assertEqual(qt.releases(['v6.12.0', 'v6.12.0-beta1', 'v6.8.0-lts-lgpl', 'v5.15.2'], qt.members[0]), {'6.12.0'})
        holder = groups.Member('lib/h', 'x', 'h', 'vulkan-sdk-{}', literal=True)
        self.assertEqual(holder.version_in('https://x/refs/tags/vulkan-sdk-1.4.357.0.tar.gz\n'), '1.4.357.0')


if __name__ == '__main__':
    unittest.main()
