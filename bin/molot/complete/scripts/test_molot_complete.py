import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    'molot_complete', Path(__file__).with_name('molot_complete.py'),
)
molot_complete = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = molot_complete
SPEC.loader.exec_module(molot_complete)


def copy_uids(records, out, stats=None, cutoff=100):
    for record in records:
        record.setdefault('lastModified', '1970-01-01T00:01:40Z')

    return molot_complete.copy_uids(
        [json.dumps(record) for record in records], out, stats or {}, cutoff,
    )


class MolotCompleteTests(unittest.TestCase):
    def test_copy_uids_emits_etag_column_in_ls_order(self):
        records = [
            {'status': 'success', 'type': 'file', 'key': 'b/result.zstd', 'etag': '"beef"'},
            {'status': 'success', 'type': 'file', 'key': 'a/result.zstd', 'etag': 'cafe'},
        ]
        out = io.StringIO()

        count = copy_uids(records, out)

        self.assertEqual(count, 2)
        self.assertEqual(out.getvalue(), 'b beef\na cafe\n')

    def test_copy_uids_degrades_to_bare_uid_without_usable_etag(self):
        records = [
            {'status': 'success', 'type': 'file', 'key': 'a/result.zstd', 'etag': ''},
            {'status': 'success', 'type': 'file', 'key': 'b/result.zstd', 'etag': 'dead-2'},
        ]
        out = io.StringIO()

        count = copy_uids(records, out)

        self.assertEqual(count, 2)
        self.assertEqual(out.getvalue(), 'a\nb\n')

    def test_copy_uids_skips_folders_and_foreign_files(self):
        records = [
            {'status': 'success', 'type': 'folder', 'key': 'a/'},
            {'status': 'success', 'type': 'file', 'key': 'a/stdout', 'etag': 'ff'},
            {'status': 'success', 'type': 'file', 'key': 'a/result.zstd', 'etag': 'aa'},
        ]
        out = io.StringIO()

        count = copy_uids(records, out)

        self.assertEqual(count, 1)
        self.assertEqual(out.getvalue(), 'a aa\n')

    def test_copy_uids_rejects_failed_records(self):
        record = {'status': 'error', 'type': 'file', 'key': 'a/result.zstd'}

        with self.assertRaisesRegex(RuntimeError, 'unexpected minio ls record'):
            copy_uids([record], io.StringIO())

    @patch.object(molot_complete.subprocess, 'run')
    def test_cleanup_uses_stats_or_object_age_and_omits_deleted_uids(self, run):
        records = [
            {'status': 'success', 'type': 'file', 'key': uid + '/result.zstd',
             'lastModified': '1970-01-01T00:00:01Z'}
            for uid in ('expired', 'recent', 'untracked_old', 'boundary')
        ]
        records.append({'status': 'success', 'type': 'file', 'key': 'untracked_new/result.zstd'})
        out = io.StringIO()

        count = copy_uids(records, out, {'expired': 99, 'recent': 101, 'boundary': 100})

        self.assertEqual(count, 3)
        self.assertEqual(out.getvalue(), 'recent\nboundary\nuntracked_new\n')
        self.assertEqual(run.call_args_list, [
            unittest.mock.call(
                ('minio-client', 'rm', '--recursive', '--force', molot_complete.SOURCE + uid + '/'),
                check=True,
            )
            for uid in ('expired', 'untracked_old')
        ])

    @patch.object(molot_complete.subprocess, 'run', side_effect=RuntimeError('delete failed'))
    def test_delete_failure_aborts(self, run):
        out = io.StringIO()
        record = {'status': 'success', 'type': 'file', 'key': 'old/result.zstd'}

        with self.assertRaisesRegex(RuntimeError, 'delete failed'):
            copy_uids([record], out, {'old': 1})

        self.assertEqual(out.getvalue(), '')

    @patch.object(molot_complete.subprocess, 'run')
    def test_cleanup_rejects_unsafe_uid(self, run):
        for uid in ('.', '..', '\\bad'):
            record = {'status': 'success', 'type': 'file', 'key': uid + '/result.zstd'}

            with self.assertRaisesRegex(RuntimeError, 'invalid result key'):
                copy_uids([record], io.StringIO(), {uid: 1})

        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
