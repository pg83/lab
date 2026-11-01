import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class VersionFilterTests(unittest.TestCase):
    def select(self, records):
        here = Path(__file__).resolve().parent
        env = dict(os.environ, PYTHONPATH=str(here.parents[3] / 'repology' / 'scripts'))
        result = subprocess.run(
            [sys.executable, '-B', str(here / 'flt.py')],
            input='\n'.join(json.dumps(r) for r in records),
            text=True, capture_output=True, check=True, env=env,
        )
        return [json.loads(line) for line in result.stdout.splitlines()]

    def test_patched_bash_wins_over_older_numeric_versions(self):
        records = [dict(pkg_name='bash', pkg_ver=v, ix_pkg_name=f'bin/bash/{v}')
                   for v in ('3.2.57', '4.4.18', '5.1.16', '5.3', '5.3p20')]
        self.assertEqual(self.select(records), [records[-1]])

    def test_keeps_all_variants_at_the_highest_patchlevel(self):
        records = [dict(pkg_name='readline', pkg_ver=v, ix_pkg_name=f'lib/readline/{i}')
                   for i, v in enumerate(('8.3', '8.3p3', '8.3p6', '8.3p6'))]
        self.assertEqual(self.select(records), records[-2:])

    def test_prereleases_remain_below_the_final_release(self):
        records = [dict(pkg_name='foo', pkg_ver=v, ix_pkg_name=f'lib/foo/{v}')
                   for v in ('1.9', '2.0rc1', '2.0')]
        self.assertEqual(self.select(records), [records[-1]])

    def test_failed_export_preserves_previous_metadata(self):
        here = Path(__file__).resolve().parent

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dump = root / 'pkgs/die/scripts/dump.json'
            dump.parent.mkdir(parents=True)
            dump.write_text('previous complete metadata\n')
            source = root / 'ix'
            source.write_text('#!/bin/sh\nprintf "partial output\\n"\nexit 7\n')
            source.chmod(0o755)
            helpers = root / 'bin'
            helpers.mkdir()

            for name in ('ix_repo', 'ix_flt'):
                path = helpers / name
                path.write_text('#!/bin/sh\nexec cat\n')
                path.chmod(0o755)

            env = dict(os.environ, PATH=str(helpers) + os.pathsep + os.environ['PATH'])
            result = subprocess.run([str(here / 'repo_export.sh')], cwd=root, env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(dump.read_text(), 'previous complete metadata\n')
            self.assertEqual(list(dump.parent.iterdir()), [dump])


if __name__ == '__main__':
    unittest.main()
