#!/usr/bin/env python3

import importlib.util
import base64
import io
import json
import os
import signal
import subprocess
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
                'ETCD_PERSIST_ENDPOINTS',
                'GIT_USER',
                'IX_FIXER_CODEX_GORN_API',
                'IX_FIXER_CODEX_S3_ENDPOINT',
                'IX_FIXER_GENERATION',
            )
        }
        env['IX_FIXER_GENERATION'] = fixer.FIXER_GENERATION
        return env

    def init_git_repo(self, root):
        repo = Path(root) / 'repo'
        subprocess.run(('git', 'init', '-q', str(repo)), check=True)
        subprocess.run(('git', 'config', 'user.name', 'test'), cwd=repo, check=True)
        subprocess.run(('git', 'config', 'user.email', 'test@example.invalid'), cwd=repo, check=True)
        (repo / 'README').write_text('base\n')
        subprocess.run(('git', 'add', 'README'), cwd=repo, check=True)
        subprocess.run(
            ('git', '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', 'base'),
            cwd=repo,
            check=True,
        )
        base = subprocess.check_output(
            ('git', 'rev-parse', 'HEAD'), cwd=repo, text=True,
        ).strip()
        return repo, base

    def commit_file(self, repo, path, contents, message):
        (repo / path).write_text(contents)
        subprocess.run(('git', 'add', path), cwd=repo, check=True)
        subprocess.run(
            ('git', '-c', 'commit.gpgsign=false', 'commit', '-q', '-m', message),
            cwd=repo,
            check=True,
        )
        return subprocess.check_output(
            ('git', 'rev-parse', 'HEAD'), cwd=repo, text=True,
        ).strip()

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

    def test_prompt_asks_for_one_local_commit_without_publication(self):
        prompt = fixer.codex_prompt(fixer.IX_TARGET, 'node failed: root')
        compact = ' '.join(prompt.split())
        self.assertIn('./ix build set/ci/tier/0 --seed=1', compact)
        self.assertIn('./ix build <package> --seed=1', compact)
        self.assertIn('as often as needed', compact)
        self.assertIn('until that build exits zero', compact)
        self.assertIn('one local commit with a concise factual message', compact)
        self.assertIn('prefer fixing that dependency', compact)
        self.assertIn('only one consumer is incompatible', compact)
        self.assertIn('Revert the dependency update only', compact)
        self.assertIn('add the `noauto` marker', compact)
        self.assertNotIn('Repository HEAD', prompt)
        self.assertNotIn('without -k', prompt)
        self.assertNotIn('supervisor', prompt)
        self.assertNotIn('credentials', prompt)
        self.assertNotIn('Do not fetch', prompt)
        self.assertNotIn('IX_EXEC_KIND', prompt)
        self.assertNotIn('Molot', prompt)
        self.assertNotIn('build <package> -k', prompt)

    def test_fixer_target_is_fixed_to_tier_zero(self):
        self.assertEqual(fixer.IX_TARGET, 'set/ci/tier/0')

        proc = mock.Mock()
        proc.stdout = io.BytesIO(b'green\n')
        proc.wait.return_value = 0

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(fixer.subprocess, 'Popen', return_value=proc) as popen, \
             mock.patch.object(fixer, 'stream_file'):
            repo = Path(td)
            env = self.run_env()
            env['IX_FIXER_TARGET'] = 'set/ci'
            fixer.run_build(repo, repo / 'cache', env)

        self.assertEqual(
            popen.call_args.args[0],
            ('./ix', 'build', 'set/ci/tier/0', '--seed=1'),
        )

    def test_build_stops_at_first_direct_failure(self):
        proc = mock.Mock()
        proc.stdout = io.BytesIO(
            b'ready\n'
            b'\x1b[91mnode failed: direct root cause\x1b[0m\n'
            b'must not be consumed\n'
        )

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(fixer.subprocess, 'Popen', return_value=proc), \
             mock.patch.object(fixer, 'stop_build_process_group', return_value=-15) as stop, \
             mock.patch.object(fixer, 'stream_file'):
            repo = Path(td)
            returncode, build_log = fixer.run_build(repo, repo / 'cache', self.run_env())
            build_log_bytes = build_log.read_bytes()

        self.assertEqual(returncode, -15)
        self.assertEqual(
            build_log_bytes,
            b'ready\n\x1b[91mnode failed: direct root cause\x1b[0m\n',
        )
        stop.assert_called_once_with(proc)

    def test_stop_build_process_group_terminates_the_session(self):
        proc = mock.Mock(pid=1234, returncode=None)
        proc.poll.return_value = None
        proc.wait.return_value = -signal.SIGTERM

        with mock.patch.object(fixer.os, 'killpg') as killpg:
            returncode = fixer.stop_build_process_group(proc)

        self.assertEqual(returncode, -signal.SIGTERM)
        killpg.assert_called_once_with(1234, signal.SIGTERM)
        proc.wait.assert_called_once_with(timeout=fixer.BUILD_STOP_TIMEOUT_S)

    def test_codex_runs_noninteractively_without_external_profile(self):
        cmd = fixer.codex_command(Path('/work/ix'), 'repair it')
        self.assertEqual(cmd[:4], ('timeout', '7200', 'codex', 'exec'))
        self.assertIn('--model', cmd)
        self.assertEqual(cmd[cmd.index('--model') + 1], 'gpt-5.6-sol')
        self.assertIn('--config', cmd)
        self.assertEqual(
            cmd[cmd.index('--config') + 1],
            'model_reasoning_effort="xhigh"',
        )
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
                auth,
            )
            auth_path = home / 'auth.json'
            config_path = home / 'config.toml'
            self.assertEqual(auth_path.read_bytes(), auth)
            self.assertEqual(
                config_path.read_text(),
                'allow_login_shell = false\n'
                '\n'
                '[shell_environment_policy]\n'
                'inherit = "all"\n',
            )
            self.assertEqual(home.stat().st_mode & 0o777, 0o700)
            self.assertEqual(auth_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(config_path.stat().st_mode & 0o777, 0o600)

    def test_codex_auth_etcd_envelope_is_authenticated(self):
        auth = b'{"tokens":{"access_token":"secret"}}\n'
        key = bytes(range(32))
        seed_hash = '1' * 64
        encrypted = fixer.encrypt_codex_auth(auth, key, seed_hash)
        decrypted, got_seed_hash = fixer.decrypt_codex_auth(encrypted, key)
        self.assertEqual(decrypted, auth)
        self.assertEqual(got_seed_hash, seed_hash)

        envelope = json.loads(encrypted)
        tag = bytearray(base64.b64decode(envelope['tag']))
        tag[0] ^= 1
        envelope['tag'] = base64.b64encode(tag).decode()

        with self.assertRaisesRegex(
            fixer.InfrastructureFailure,
            'authentication failed',
        ):
            fixer.decrypt_codex_auth(json.dumps(envelope).encode(), key)

    def test_codex_auth_key_rotation_uses_bootstrap(self):
        auth = b'{"tokens":{"access_token":"old"}}\n'
        encrypted = fixer.encrypt_codex_auth(auth, bytes(range(32)), '1' * 64)
        self.assertEqual(
            fixer.decrypt_codex_auth(encrypted, bytes(range(1, 33))),
            (None, None),
        )

    def test_codex_auth_bootstrap_rotation_replaces_runtime(self):
        old_auth = b'{"tokens":{"access_token":"old"}}\n'
        new_auth = b'{"tokens":{"access_token":"new"}}\n'
        key = bytes(range(32))
        encrypted = fixer.encrypt_codex_auth(
            old_auth,
            key,
            fixer.hashlib.sha256(old_auth).hexdigest(),
        )

        with mock.patch.object(fixer, 'load_codex_wrapping_key', return_value=key), \
             mock.patch.object(fixer, 'load_codex_bootstrap', return_value=new_auth), \
             mock.patch.object(fixer, 'read_codex_auth_etcd', return_value=encrypted):
            got, got_key, seed_hash = fixer.load_codex_auth(self.run_env())

        self.assertEqual(got, new_auth)
        self.assertEqual(got_key, key)
        self.assertEqual(seed_hash, fixer.hashlib.sha256(new_auth).hexdigest())

    def test_codex_auth_uses_persistent_etcd(self):
        env = self.run_env()
        env['ETCDCTL_ENDPOINTS'] = 'tmpfs:2379'
        env['ETCD_PERSIST_ENDPOINTS'] = 'persist:2379'
        result = mock.Mock(returncode=0, stdout=b'', stderr=b'')

        with mock.patch.object(fixer.subprocess, 'run', return_value=result) as run:
            self.assertEqual(fixer.read_codex_auth_etcd(env), b'')

        self.assertEqual(
            run.call_args.kwargs['env']['ETCDCTL_ENDPOINTS'],
            'persist:2379',
        )

    def test_refreshed_auth_is_saved_even_when_codex_fails(self):
        auth = b'{"tokens":{"access_token":"secret"}}\n'
        key = bytes(range(32))

        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / 'ix'
            repo.mkdir()
            build_log = repo / '.fixer-build.log'
            build_log.write_text('node failed: root\n')

            with mock.patch.object(
                fixer.subprocess,
                'check_output',
                return_value='abc123\n',
            ), mock.patch.object(
                fixer,
                'load_codex_auth',
                return_value=(auth, key, '1' * 64),
            ), mock.patch.object(
                fixer.subprocess,
                'run',
                side_effect=fixer.subprocess.CalledProcessError(1, 'codex'),
            ), mock.patch.object(fixer, 'save_codex_auth') as save:
                with self.assertRaises(fixer.subprocess.CalledProcessError):
                    fixer.run_codex(repo, repo / 'cache', build_log, self.run_env())

            save.assert_called_once()
            self.assertEqual(save.call_args.args[0], auth)

    def test_codex_agent_uses_cluster_endpoints_inside_wirez(self):
        env = self.run_env()
        env['GORN_API'] = 'http://127.0.0.1:8025'
        env['S3_ENDPOINT'] = 'http://127.0.0.1:8012'
        env['IX_FIXER_CODEX_GORN_API'] = 'http://192.168.100.16:8027'
        env['IX_FIXER_CODEX_S3_ENDPOINT'] = 'http://192.168.103.16:8012'

        with tempfile.TemporaryDirectory() as td:
            got = fixer.codex_agent_env(
                env,
                Path(td) / 'cache',
                Path(td) / 'codex-home',
            )

        self.assertEqual(got['GORN_API'], 'http://192.168.100.16:8027')
        self.assertEqual(got['S3_ENDPOINT'], 'http://192.168.103.16:8012')
        self.assertEqual(got['IX_EXEC_KIND'], 'molot')
        self.assertNotIn('ETCD_PERSIST_ENDPOINTS', got)
        self.assertNotIn('GIT_USER', got)
        self.assertNotIn('GIT_PASS', got)
        self.assertNotIn('GIT_ASKPASS', got)
        self.assertEqual(got['GIT_TERMINAL_PROMPT'], '0')
        self.assertNotIn('CODEX_AUTH_B64', got)

    def test_clone_does_not_receive_repository_credentials(self):
        env = self.run_env()

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(fixer.subprocess, 'run') as run:
            repo = Path(td) / 'ix'
            (repo / '.git' / 'info').mkdir(parents=True)
            fixer.clone_ix(repo, env)

        clone_env = run.call_args_list[0].kwargs['env']
        self.assertNotIn('GIT_USER', clone_env)
        self.assertNotIn('GIT_PASS', clone_env)
        self.assertNotIn('GIT_ASKPASS', clone_env)
        self.assertEqual(clone_env['GIT_TERMINAL_PROMPT'], '0')
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(
            commands[0],
            (
                'git', 'clone', '--single-branch', '--branch', 'main',
                fixer.IX_GIT_READ_URL, str(repo),
            ),
        )
        self.assertIn(
            (
                'git', 'remote', 'set-url', '--push', 'origin',
                fixer.IX_GIT_PUSH_URL,
            ),
            commands,
        )

    def test_publish_uses_supervisor_credentials_after_agent(self):
        env = self.run_env()
        ok = mock.Mock(returncode=0)

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(fixer, 'validate_agent_commit', return_value='fix123'), \
             mock.patch.object(
                 fixer, 'git_output', side_effect=('abc123', 'abc123'),
             ), \
             mock.patch.object(
                 fixer, 'amend_repository_metadata', return_value='amended123',
             ) as amend, \
             mock.patch.object(fixer, 'load_repo_token', return_value='repo-token'):
            repo = Path(td)

            with mock.patch.object(fixer.subprocess, 'run', return_value=ok) as run:
                self.assertTrue(fixer.publish_fix(repo, 'abc123', 'main', env))

        calls = run.call_args_list
        push = next(call for call in calls if 'push' in call.args[0])
        fetch = next(call for call in calls if call.args[0][:2] == ('git', 'fetch'))
        self.assertEqual(fetch.args[0], ('git', 'fetch', 'origin', 'main'))
        self.assertIn('origin', push.args[0])
        self.assertIn('amended123:refs/heads/main', push.args[0])
        self.assertNotIn('--force', push.args[0])
        self.assertEqual(push.kwargs['env']['GIT_ASKPASS'], 'passenv')
        self.assertEqual(push.kwargs['env']['GIT_PASS'], 'repo-token')
        self.assertNotIn('GIT_PASS', fetch.kwargs['env'])
        self.assertFalse(any('commit' in call.args[0] for call in calls))
        self.assertFalse(any('rebase' in call.args[0] for call in calls))
        amend.assert_called_once_with(repo, env)

    def test_publish_rebases_and_pushes_when_remote_moved(self):
        env = self.run_env()
        ok = mock.Mock(returncode=0)

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(fixer, 'validate_agent_commit', return_value='fix123'), \
             mock.patch.object(
                 fixer, 'git_output', side_effect=('moved', 'original'),
             ), \
             mock.patch.object(
                 fixer, 'amend_repository_metadata', return_value='rebased',
             ), \
             mock.patch.object(fixer, 'load_repo_token', return_value='repo-token'), \
             mock.patch.object(fixer.subprocess, 'run', return_value=ok) as run:
            self.assertTrue(fixer.publish_fix(Path(td), 'original', 'main', env))

        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn(('git', 'rebase', 'FETCH_HEAD'), commands)
        push = next(command for command in commands if 'push' in command)
        self.assertIn('rebased:refs/heads/main', push)
        self.assertNotIn('--force', push)

    def test_publish_rebuilds_stats_after_push_race(self):
        env = self.run_env()
        pushes = 0

        def run_result(command, **kwargs):
            nonlocal pushes

            if 'push' in command:
                pushes += 1
                return mock.Mock(returncode=1 if pushes == 1 else 0)

            return mock.Mock(returncode=0)

        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(fixer, 'validate_agent_commit', return_value='fix123'), \
             mock.patch.object(
                 fixer,
                 'git_output',
                 side_effect=('base', 'base', 'moved', 'base'),
             ), \
             mock.patch.object(
                 fixer,
                 'amend_repository_metadata',
                 side_effect=('first-amended', 'second-amended'),
             ) as amend, \
             mock.patch.object(fixer, 'remove_repository_metadata_from_commit') as remove, \
             mock.patch.object(fixer, 'load_repo_token', return_value='repo-token'), \
             mock.patch.object(fixer.time, 'sleep') as sleep, \
             mock.patch.object(fixer.subprocess, 'run', side_effect=run_result) as run:
            repo = Path(td)
            self.assertTrue(fixer.publish_fix(repo, 'base', 'main', env))

        self.assertEqual(amend.call_count, 2)
        remove.assert_called_once_with(repo)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(sum('push' in command for command in commands), 2)
        self.assertIn(('git', 'rebase', 'FETCH_HEAD'), commands)
        sleep.assert_called_once_with(fixer.GIT_MIRROR_RETRY_DELAY_S)

    def test_amend_repository_metadata_rebuilds_generated_files(self):
        with tempfile.TemporaryDirectory() as td, \
             mock.patch.object(fixer, 'regenerate_repository_metadata') as regenerate, \
             mock.patch.object(fixer.subprocess, 'run') as run, \
             mock.patch.object(fixer, 'git_output', return_value='amended'):
            repo = Path(td)
            self.assertEqual(
                fixer.amend_repository_metadata(repo, self.run_env()),
                'amended',
            )

        regenerate.assert_called_once_with(repo, self.run_env())
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(
            commands,
            [
                ('git', 'add', '--', *fixer.REGENERATED_PATHS),
                ('git', 'commit', '--amend', '--no-edit'),
            ],
        )

    def test_validate_accepts_one_clean_agent_commit(self):
        with tempfile.TemporaryDirectory() as td:
            repo, base = self.init_git_repo(td)
            head = self.commit_file(
                repo,
                'recipe',
                'fixed\n',
                'fix exfat-progs configure flags',
            )
            self.assertEqual(fixer.validate_agent_commit(repo, base), head)

    def test_validate_accepts_clean_noop(self):
        with tempfile.TemporaryDirectory() as td:
            repo, base = self.init_git_repo(td)
            self.assertIsNone(fixer.validate_agent_commit(repo, base))

    def test_validate_rejects_uncommitted_changes(self):
        with tempfile.TemporaryDirectory() as td:
            repo, base = self.init_git_repo(td)
            (repo / 'recipe').write_text('dirty\n')

            with self.assertRaisesRegex(
                fixer.InfrastructureFailure,
                'uncommitted repository changes',
            ):
                fixer.validate_agent_commit(repo, base)

    def test_validate_rejects_multiple_agent_commits(self):
        with tempfile.TemporaryDirectory() as td:
            repo, base = self.init_git_repo(td)
            self.commit_file(repo, 'one', 'one\n', 'first fix')
            self.commit_file(repo, 'two', 'two\n', 'second fix')

            with self.assertRaisesRegex(
                fixer.InfrastructureFailure,
                'exactly one commit',
            ):
                fixer.validate_agent_commit(repo, base)

    def test_validate_rejects_empty_agent_commit(self):
        with tempfile.TemporaryDirectory() as td:
            repo, base = self.init_git_repo(td)
            subprocess.run(
                (
                    'git', '-c', 'commit.gpgsign=false',
                    'commit', '-q', '--allow-empty', '-m', 'pretend fix',
                ),
                cwd=repo,
                check=True,
            )

            with self.assertRaisesRegex(
                fixer.InfrastructureFailure,
                'empty repair commit',
            ):
                fixer.validate_agent_commit(repo, base)

    def test_required_environment_does_not_require_codex_package_variable(self):
        env = self.run_env()
        fixer.require_env(env)
        self.assertNotIn('CODEX_HOME', env)

    def test_obsolete_generation_exits_before_work(self):
        env = self.run_env()
        env['IX_FIXER_GENERATION'] = '1'

        with self.assertRaisesRegex(fixer.InfrastructureFailure, 'obsolete fixer generation'):
            fixer.require_env(env)

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
             mock.patch.object(fixer, 'run_codex', return_value='abc123') as codex, \
             mock.patch.object(fixer, 'publish_fix') as publish:
            fixer.run_fixer(self.run_env())

        codex.assert_called_once()
        publish.assert_called_once()
        merge.assert_called_once()


if __name__ == '__main__':
    unittest.main()
