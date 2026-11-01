import contextlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('fetch', Path(__file__).with_name('fetch.py'))
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)

BASE = 'a' * 40
HEAD = 'b' * 40


class CursorTest(unittest.TestCase):
    def test_merge_with_identical_tree_has_no_new_urls(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.chdir(tmp):
            def git(*args):
                return subprocess.check_output(['git', '-C', 'repo', *args], stderr=subprocess.PIPE, text=True).strip()

            subprocess.run(['git', 'init', '-q', '-b', 'stable', 'repo'], check=True)
            git('config', 'user.name', 'Test')
            git('config', 'user.email', 'test@example.com')
            urls = Path('repo', fetch.URLS_PATH)
            urls.parent.mkdir(parents=True)
            urls.write_text('https://example.org/old\n')
            git('add', '.')
            git('commit', '-qm', 'stable')
            git('checkout', '-qb', 'development')
            urls.write_text(urls.read_text() + 'https://example.org/new\n')
            git('commit', '-qam', 'development')
            processed = git('rev-parse', 'HEAD')
            git('checkout', '-q', 'stable')
            git('merge', '--no-ff', '-qm', 'stable merge', 'development')
            merged = git('rev-parse', 'HEAD')
            with patch.object(fetch, 'MIRROR_GIT', str(Path('repo').resolve())):
                fetch.clone_repo(merged)
            self.assertTrue(fetch.is_ancestor(processed, merged))
            self.assertEqual(fetch.added_urls(processed, merged), [])
            urls.write_text(urls.read_text() + 'https://example.org/later\n')
            git('commit', '-qam', 'later')
            latest = git('rev-parse', 'HEAD')
            subprocess.run(['git', '-C', 'ix.git', 'fetch', '-q', 'origin', 'stable'], check=True)
            self.assertEqual(fetch.added_urls(processed, latest), ['https://example.org/later'])

    def test_old_event_does_not_rewind(self):
        with patch.object(fetch, 'read_cursor', return_value=BASE), \
                patch.object(fetch, 'clone_repo'), \
                patch.object(fetch, 'is_ancestor', return_value=True), \
                patch.object(fetch, 'fetch_urls') as download, \
                patch.object(fetch, 'save_cursor') as save:
            fetch.process_commit(HEAD)
            download.assert_not_called()
            save.assert_not_called()

    def test_cursor_is_saved_only_after_download_and_event(self):
        calls = []
        with patch.object(fetch, 'read_cursor', return_value=BASE), \
                patch.object(fetch, 'clone_repo'), \
                patch.object(fetch, 'is_ancestor', side_effect=[False, True]), \
                patch.object(fetch, 'added_urls', return_value=['https://example.org/new']), \
                patch.object(fetch, 'fetch_one', side_effect=lambda _: calls.append('download') or 'sha'), \
                patch.object(fetch, 'emit_new_sha', side_effect=lambda _: calls.append('event')), \
                patch.object(fetch, 'save_cursor', side_effect=lambda *_: calls.append('cursor')):
            fetch.process_commit(HEAD)
            self.assertEqual(calls, ['download', 'event', 'cursor'])

    def test_failure_keeps_cursor(self):
        for failing in ('fetch_one', 'emit_new_sha'):
            with self.subTest(failing=failing), \
                    patch.object(fetch, 'read_cursor', return_value=BASE), \
                    patch.object(fetch, 'clone_repo'), \
                    patch.object(fetch, 'is_ancestor', side_effect=[False, True]), \
                    patch.object(fetch, 'added_urls', return_value=['https://example.org/new']), \
                    patch.object(fetch, 'fetch_one', return_value='sha'), \
                    patch.object(fetch, failing, side_effect=subprocess.CalledProcessError(22, failing)), \
                    patch.object(fetch, 'save_cursor') as save:
                with self.assertRaises(subprocess.CalledProcessError):
                    fetch.process_commit(HEAD)
                save.assert_not_called()

    def test_missing_cursor_does_not_scan_history(self):
        with patch.dict(os.environ, ETCD_PERSIST_ENDPOINTS='persistent:8020'), \
                patch.object(fetch.subprocess, 'check_output', return_value=''), \
                patch.object(fetch, 'clone_repo') as clone:
            with self.assertRaisesRegex(RuntimeError, 'seed it'):
                fetch.process_commit(HEAD)
            clone.assert_not_called()

    def test_diverged_history_keeps_cursor(self):
        with patch.object(fetch, 'read_cursor', return_value=BASE), \
                patch.object(fetch, 'clone_repo'), \
                patch.object(fetch, 'is_ancestor', return_value=False), \
                patch.object(fetch, 'save_cursor') as save:
            with self.assertRaisesRegex(RuntimeError, 'diverged'):
                fetch.process_commit(HEAD)
            save.assert_not_called()

    def test_lost_lock_rejects_cursor_write(self):
        with patch.dict(os.environ, ETCD_PERSIST_ENDPOINTS='persistent:8020',
                        ETCDCTL_ENDPOINTS='ephemeral:8042', ETCD_LOCK_KEY=fetch.LOCK_NAME + '/lease'), \
                patch.object(fetch.subprocess, 'check_output', return_value='{"succeeded": false}') as txn:
            with self.assertRaisesRegex(RuntimeError, 'lock expired'):
                fetch.save_cursor(BASE, HEAD)
            self.assertEqual(txn.call_args.kwargs['env']['ETCDCTL_ENDPOINTS'], 'persistent:8020')
            self.assertIn(f'version("{fetch.LOCK_NAME}/lease") > "0"', txn.call_args.kwargs['input'])
            self.assertIn(f'value("{fetch.CURSOR_KEY}") = "{BASE}"', txn.call_args.kwargs['input'])


if __name__ == '__main__':
    unittest.main()
