#!/usr/bin/env python3

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SPEC = importlib.util.spec_from_file_location('merger', Path(__file__).with_name('merger.py'))
merger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(merger)


class MergerTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.author = self.root / 'author'
        self.source = self.root / 'source.git'
        self.target = self.root / 'target.git'
        self.author.mkdir()
        self.git(self.author, 'init', '-b', 'main')
        self.git(self.author, 'config', 'user.name', 'fixture')
        self.git(self.author, 'config', 'user.email', 'fixture@example.invalid')
        (self.author / 'ix').write_text('#!/bin/sh\ntest "$*" = "build set/ci/tier/0 --seed=1"\n')
        (self.author / 'ix').chmod(0o755)
        self.base = self.commit(self.author, 'recipe', 'old\n')
        self.git(self.root, 'clone', '--bare', str(self.author), str(self.target))
        self.source_head = self.commit(self.author, 'recipe', 'new\n')
        self.git(self.root, 'clone', '--bare', str(self.author), str(self.source))
        self.env = dict(os.environ, IX_MERGER_MIRROR_URL=str(self.source),
                        IX_MERGER_SOURCE_URL=str(self.source),
                        IX_MERGER_TARGET_URL=str(self.target))
        self.token = mock.patch.object(merger, 'load_token', return_value='test-token').start()
        self.addCleanup(mock.patch.stopall)
        api = mock.patch.object(merger, 'GitHub').start()
        self.pr = api.return_value.stable_pr
        self.pr.side_effect = lambda branch, source, base, tree: {
            'number': 123, 'html_url': 'https://example.invalid/pull/123',
        }
        mock.patch.object(merger, 'RETRY_DELAY_S', 0).start()

    def git(self, repo, *args):
        return subprocess.check_output(
            ('git', '-c', 'commit.gpgsign=false', *args), cwd=repo, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()

    def commit(self, repo, path, text):
        (repo / path).write_text(text)
        self.git(repo, 'add', '.')
        self.git(repo, 'commit', '-m', 'fixture')
        return self.git(repo, 'rev-parse', 'HEAD')

    def worker(self, name='worker'):
        return merger.Merger(self.root / name, self.env)

    def move_target(self, filename='stable-only', content='stable change\n'):
        repo = self.root / 'stable-author'
        self.git(self.root, 'clone', str(self.target), str(repo))
        self.git(repo, 'config', 'user.name', 'fixture')
        self.git(repo, 'config', 'user.email', 'fixture@example.invalid')
        head = self.commit(repo, filename, content)
        self.git(repo, 'push', 'origin', 'main')
        return head

    def test_green_build_publishes_two_parent_bot_merge(self):
        self.worker().run()
        parents = self.git(self.target, 'rev-list', '--parents', '-n', '1', 'main').split()[1:]
        self.assertEqual(parents, [self.base, self.source_head])
        identity = self.git(self.target, 'show', '-s', '--format=%ae%n%ce', 'main').splitlines()
        self.assertEqual(identity, [merger.BOT_EMAIL, merger.BOT_EMAIL])
        self.assertEqual(self.git(self.target, 'rev-parse', 'main^{tree}'),
                         self.git(self.source, 'rev-parse', self.source_head + '^{tree}'))
        self.assertIn('Merge pull request #123', self.git(self.target, 'show', '-s', '--format=%B', 'main'))

    def test_failed_full_build_never_loads_token_or_publishes(self):
        self.commit(self.author, 'ix', '#!/bin/sh\nexit 7\n')
        self.git(self.author, 'push', str(self.source), 'main')
        with self.assertRaises(subprocess.CalledProcessError):
            self.worker().run()
        self.assertEqual(self.git(self.target, 'rev-parse', 'main'), self.base)
        self.token.assert_not_called()
        self.pr.assert_not_called()

    def test_new_development_commit_is_not_silently_included(self):
        worker = self.worker()
        build = worker.build
        def concurrent_update():
            build()
            self.commit(self.author, 'recipe', 'unbuilt development change\n')
            self.git(self.author, 'push', str(self.source), 'main')
        worker.build = concurrent_update
        worker.run()
        self.assertEqual(self.git(self.target, 'rev-parse', 'main^2'), self.source_head)
        self.assertEqual(self.git(self.target, 'show', 'main:recipe'), 'new')

    def test_moving_stable_during_build_requires_another_full_build(self):
        worker = self.worker()
        build = worker.build
        built = []
        bases = []
        def concurrent_update():
            build()
            built.append(self.git(worker.repo, 'rev-parse', 'HEAD^{tree}'))
            if len(built) == 1:
                bases.append(self.move_target())
        worker.build = concurrent_update
        worker.run()
        self.assertEqual(len(built), 2)
        self.assertNotEqual(built[0], built[1])
        self.assertEqual(self.git(self.target, 'rev-parse', 'main^1'), bases[0])
        self.assertEqual(self.git(self.target, 'rev-parse', 'main^{tree}'), built[1])

    def test_target_push_race_rebuilds_instead_of_rebasing_green_commit(self):
        worker = self.worker()
        git = worker.git
        raced = []
        def concurrent_push(*args, **kwargs):
            if args[:2] == ('push', str(self.target)) and not raced:
                raced.append(self.move_target())
            return git(*args, **kwargs)
        worker.git = concurrent_push
        with mock.patch.object(worker, 'build', wraps=worker.build) as build:
            worker.run()
        self.assertEqual(build.call_count, 2)
        self.assertEqual(self.git(self.target, 'rev-parse', 'main^1'), raced[0])
        self.assertEqual(self.git(self.target, 'show', 'main:stable-only'), 'stable change')

    def test_already_promoted_source_does_not_make_an_empty_merge(self):
        self.worker().run()
        stable = self.git(self.target, 'rev-parse', 'main')
        worker = self.worker('second-worker')
        with mock.patch.object(worker, 'build') as build:
            worker.run()
        build.assert_not_called()
        self.assertEqual(self.git(self.target, 'rev-parse', 'main'), stable)

    def test_conflict_leaves_stable_unchanged(self):
        stable = self.move_target('recipe', 'conflicting stable change\n')
        worker = self.worker()
        with mock.patch.object(worker, 'build') as build:
            with self.assertRaises(subprocess.CalledProcessError):
                worker.run()
        build.assert_not_called()
        self.token.assert_not_called()
        self.assertEqual(self.git(self.target, 'rev-parse', 'main'), stable)

    def test_build_cannot_publish_a_different_tracked_tree(self):
        self.commit(self.author, 'ix', '#!/bin/sh\nprintf changed > recipe\n')
        self.git(self.author, 'push', str(self.source), 'main')
        with self.assertRaises(subprocess.CalledProcessError):
            self.worker().run()
        self.assertEqual(self.git(self.target, 'rev-parse', 'main'), self.base)
        self.token.assert_not_called()


if __name__ == '__main__':
    unittest.main()
