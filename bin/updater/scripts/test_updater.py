#!/usr/bin/env python3

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


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

    def test_prepare_recipe_keeps_go_upgrade_rule(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'ix.sh'
            path.write_text(
                "{% block version %}1.0{% endblock %}\n"
                "{% block go_url %}https://x/v1.0.tar.gz{% endblock %}\n"
                "{% block go_sha %}\n" + 'a' * 64 + "\n{% endblock %}\n"
                "{% block go_tool %}bin/go/lang/23{% endblock %}\n"
            )

            self.assertTrue(updater.prepare_recipe(path, '1.0', '2.0'))
            data = path.read_text()
            self.assertIn('2.0', data)
            self.assertIn(updater.SENTINEL_SHA, data)
            self.assertIn('bin/go/lang/25', data)
            self.assertIn('{% block go_tool %}', data)

    def test_noauto_recipe_is_not_changed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'ix.sh'
            original = 'noauto\n1.0\n' + 'a' * 64 + '\n'
            path.write_text(original)

            self.assertFalse(updater.prepare_recipe(path, '1.0', '2.0'))
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
            b'expected=' + updater.SENTINEL_SHA.encode() + b' actual=' + actual.encode() + b'\n' +
            unrelated.encode() + b' later-noise\n'
        )

        self.assertEqual(updater.extract_reported_sha(output), actual)

    def test_extracts_colored_direct_fetch_checksum(self):
        actual = 'e' * 64
        output = (
            b'got \x1b[91m' + actual.encode() + b'\x1b[0m checksum, not ' +
            updater.SENTINEL_SHA.encode()
        )

        self.assertEqual(updater.extract_reported_sha(output), actual)

    def test_success_is_two_builds_then_commit_without_final_build(self):
        actual = 'd' * 64
        checksum_output = (
            b'molot exec: predict mismatch: predict mismatch: /x expected=' +
            updater.SENTINEL_SHA.encode() + b' actual=' + actual.encode()
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
                "{% block version %}1.0{% endblock %}\n"
                "{% block fetch %}\nhttps://x/foo-1.0.tar.gz\n" + 'a' * 64 + "\n{% endblock %}\n"
            )
            worker = FakePackageUpdater(repo, builder)
            candidate = updater.Candidate('1.0', '2.0', ('bin/foo',))

            self.assertTrue(worker.process(candidate))
            self.assertEqual(builder.calls, [['bin/foo'], ['bin/foo']])
            self.assertEqual(worker.commits, [candidate])
            self.assertIn(actual, recipe.read_text())
            self.assertNotIn(updater.SENTINEL_SHA, recipe.read_text())

    def test_failed_preflight_does_not_touch_recipe(self):
        builder = FakeBuilder([
            updater.BuildResult(2, b'node failed: bin/foo'),
        ])

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            recipe = repo / 'pkgs/bin/foo/ix.sh'
            recipe.parent.mkdir(parents=True)
            original = (
                "{% block version %}1.0{% endblock %}\n"
                "{% block fetch %}\nhttps://x/foo-1.0.tar.gz\n" + 'a' * 64 + "\n{% endblock %}\n"
            )
            recipe.write_text(original)
            worker = FakePackageUpdater(repo, builder)

            with self.assertRaises(updater.CandidateFailure):
                worker.process(updater.Candidate('1.0', '2.0', ('bin/foo',)))

            self.assertEqual(recipe.read_text(), original)
            self.assertEqual(worker.commits, [])


if __name__ == '__main__':
    unittest.main()
