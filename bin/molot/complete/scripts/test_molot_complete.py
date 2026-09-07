import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    'molot_complete', Path(__file__).with_name('molot_complete.py'),
)
molot_complete = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = molot_complete
SPEC.loader.exec_module(molot_complete)


class MolotCompleteTests(unittest.TestCase):
    def test_copy_uids_emits_etag_column_in_ls_order(self):
        records = [
            {'status': 'success', 'type': 'file', 'key': 'b/result.zstd', 'etag': '"beef"'},
            {'status': 'success', 'type': 'file', 'key': 'a/result.zstd', 'etag': 'cafe'},
        ]
        lines = [json.dumps(record) for record in records]
        out = io.StringIO()

        count = molot_complete.copy_uids(lines, out)

        self.assertEqual(count, 2)
        self.assertEqual(out.getvalue(), 'b beef\na cafe\n')

    def test_copy_uids_degrades_to_bare_uid_without_usable_etag(self):
        records = [
            {'status': 'success', 'type': 'file', 'key': 'a/result.zstd', 'etag': ''},
            {'status': 'success', 'type': 'file', 'key': 'b/result.zstd', 'etag': 'dead-2'},
        ]
        out = io.StringIO()

        count = molot_complete.copy_uids([json.dumps(r) for r in records], out)

        self.assertEqual(count, 2)
        self.assertEqual(out.getvalue(), 'a\nb\n')

    def test_copy_uids_skips_folders_and_foreign_files(self):
        records = [
            {'status': 'success', 'type': 'folder', 'key': 'a/'},
            {'status': 'success', 'type': 'file', 'key': 'a/stdout', 'etag': 'ff'},
            {'status': 'success', 'type': 'file', 'key': 'a/result.zstd', 'etag': 'aa'},
        ]
        out = io.StringIO()

        count = molot_complete.copy_uids([json.dumps(r) for r in records], out)

        self.assertEqual(count, 1)
        self.assertEqual(out.getvalue(), 'a aa\n')

    def test_copy_uids_rejects_failed_records(self):
        record = {'status': 'error', 'type': 'file', 'key': 'a/result.zstd'}

        with self.assertRaisesRegex(RuntimeError, 'unexpected minio ls record'):
            molot_complete.copy_uids([json.dumps(record)], io.StringIO())


if __name__ == '__main__':
    unittest.main()
