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
    def test_copy_uids_preserves_ls_order(self):
        records = [
            {'status': 'success', 'type': 'folder', 'key': 'b/'},
            {'status': 'success', 'type': 'folder', 'key': 'a/'},
        ]
        lines = [json.dumps(record) for record in records]
        out = io.StringIO()

        count = molot_complete.copy_uids(lines, out)

        self.assertEqual(count, 2)
        self.assertEqual(out.getvalue(), 'b\na\n')

    def test_copy_uids_rejects_nested_prefix(self):
        record = {'status': 'success', 'type': 'folder', 'key': 'uid/nested/'}

        with self.assertRaisesRegex(RuntimeError, 'invalid UID prefix'):
            molot_complete.copy_uids([json.dumps(record)], io.StringIO())


if __name__ == '__main__':
    unittest.main()
