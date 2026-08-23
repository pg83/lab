#!/usr/bin/env python3

import importlib.util
import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SPEC = importlib.util.spec_from_file_location('fixer', Path(__file__).with_name('fixer.py'))
fixer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fixer
SPEC.loader.exec_module(fixer)


class FixerTests(unittest.TestCase):
    def run_env(self):
        env = {
            name: name.lower()
            for name in (
                'GORN_API',
                'S3_ENDPOINT',
                'AWS_ACCESS_KEY_ID',
                'AWS_SECRET_ACCESS_KEY',
                'AWS_ACCESS_KEY_ID_MOLOT',
                'AWS_SECRET_ACCESS_KEY_MOLOT',
                'ETCDCTL_ENDPOINTS',
                'GIT_USER',
                'GIT_PASS',
            )
        }
        env['CODEX_AUTH_B64'] = base64.b64encode(b'{"tokens":{}}').decode()
        return env

    def test_target_failure_recognizes_colored_molot_marker(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'log'
            path.write_bytes(b'\x1b[91mnode failed: package exploded\x1b[0m\n')
            self.assertTrue(fixer.has_target_failure(path))

    def test_infrastructure_failure_does_not_spend_agent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'log'
            path.write_text('abort: S3 is unavailable\n')
            self.assertFalse(fixer.has_target_failure(path))

    def test_summary_keeps_only_direct_failure_markers(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'log'
            path.write_text(
                '{1/3} BROKEN BY DEP deadbeef /ix/store/dependent\n'
                '---- stderr of failed node /ix/store/root ----\n'
                'node failed: root cause\n'
            )
            self.assertEqual(
                fixer.failure_summary(path),
                '---- stderr of failed node /ix/store/root ----\n'
                'node failed: root cause',
            )

    def test_molot_env_uses_worker_credentials_and_cache(self):
        env = {
            'AWS_ACCESS_KEY_ID': 'cix-key',
            'AWS_SECRET_ACCESS_KEY': 'cix-secret',
            'AWS_ACCESS_KEY_ID_MOLOT': 'molot-key',
            'AWS_SECRET_ACCESS_KEY_MOLOT': 'molot-secret',
            'CODEX_AUTH_B64': 'must-not-leak',
        }

        with tempfile.TemporaryDirectory() as td:
            got = fixer.molot_env(env, Path(td) / 'cache')

        self.assertEqual(got['IX_EXEC_KIND'], 'molot')
        self.assertEqual(got['AWS_ACCESS_KEY_ID'], 'molot-key')
        self.assertEqual(got['AWS_SECRET_ACCESS_KEY'], 'molot-secret')
        self.assertEqual(got['S3_BUCKET'], 'molot')
        self.assertTrue(got['MOLOT_CACHE'].endswith('/cache'))
        self.assertNotIn('CODEX_AUTH_B64', got)

    def test_prompt_requires_molot_validation_commit_and_safe_push(self):
        prompt = fixer.codex_prompt('set/ci', 'abc123', 'main', 'node failed: root')
        self.assertIn('./ix build <package> --seed=1', prompt)
        self.assertIn('environment is already configured for Molot', prompt)
        self.assertIn('commit the tested fix', prompt)
        self.assertIn('origin main', prompt)
        self.assertIn('never force-push', prompt)
        self.assertNotIn('build <package> -k', prompt)

    def test_codex_runs_noninteractively_without_external_profile(self):
        cmd = fixer.codex_command(Path('/work/ix'), 'repair it')
        self.assertEqual(cmd[:2], ('codex', 'exec'))
        self.assertNotIn('-p', cmd)
        self.assertIn('--dangerously-bypass-approvals-and-sandbox', cmd)
        self.assertIn('--ephemeral', cmd)
        self.assertIn('-C', cmd)
        self.assertEqual(cmd[-1], 'repair it')

    def test_codex_auth_is_materialized_privately(self):
        auth = b'{"tokens":{"access_token":"secret"}}\n'

        with tempfile.TemporaryDirectory() as td:
            home = fixer.materialize_codex_home(
                Path(td),
                {'CODEX_AUTH_B64': base64.b64encode(auth).decode()},
            )
            auth_path = home / 'auth.json'
            self.assertEqual(auth_path.read_bytes(), auth)
            self.assertEqual(home.stat().st_mode & 0o777, 0o700)
            self.assertEqual(auth_path.stat().st_mode & 0o777, 0o600)

    def test_required_environment_does_not_require_codex_package_variable(self):
        env = self.run_env()
        fixer.require_env(env)
        self.assertNotIn('CODEX_HOME', env)

    def test_green_cycle_skips_agent_and_still_merges_cache(self):
        def clone(repo, env):
            repo.mkdir()
            return 'main'

        def build(repo, cache, env):
            path = repo / '.fixer-build.log'
            path.write_text('green\n')
            return 0, path

        with mock.patch.object(fixer, 'clone_ix', side_effect=clone), \
             mock.patch.object(fixer, 'seed_cache'), \
             mock.patch.object(fixer, 'run_build', side_effect=build), \
             mock.patch.object(fixer, 'merge_cache') as merge, \
             mock.patch.object(fixer, 'run_codex') as codex:
            fixer.run_fixer(self.run_env())

        codex.assert_not_called()
        merge.assert_called_once()

    def test_target_failure_starts_one_agent_then_merges_cache(self):
        def clone(repo, env):
            repo.mkdir()
            return 'main'

        def build(repo, cache, env):
            path = repo / '.fixer-build.log'
            path.write_text('node failed: root cause\n')
            return 2, path

        with mock.patch.object(fixer, 'clone_ix', side_effect=clone), \
             mock.patch.object(fixer, 'seed_cache'), \
             mock.patch.object(fixer, 'run_build', side_effect=build), \
             mock.patch.object(fixer, 'merge_cache') as merge, \
             mock.patch.object(fixer, 'run_codex') as codex:
            fixer.run_fixer(self.run_env())

        codex.assert_called_once()
        merge.assert_called_once()


if __name__ == '__main__':
    unittest.main()
