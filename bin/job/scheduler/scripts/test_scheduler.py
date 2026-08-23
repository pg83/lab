#!/usr/bin/env python3

import importlib.util
import sys
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    'scheduler', Path(__file__).with_name('scheduler.py'),
)
scheduler = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = scheduler
SPEC.loader.exec_module(scheduler)


class SchedulerTests(unittest.TestCase):
    def test_display_command_redacts_all_forwarded_environment_values(self):
        cmd = [
            'timeout', '10s', 'gorn', 'ignite',
            '--env', 'GORN_API=http://127.0.0.1:8025',
            '--env', 'GIT_PASS=secret',
            '--env', 'MC_HOST_minio=http://user:password@127.0.0.1:8012',
            '--', 'updater', 'run',
        ]

        shown = scheduler.display_cmd(cmd)

        self.assertIn('GORN_API=<redacted>', shown)
        self.assertIn('GIT_PASS=<redacted>', shown)
        self.assertIn('MC_HOST_minio=<redacted>', shown)
        self.assertNotIn('secret', repr(shown))
        self.assertNotIn('password', repr(shown))
        self.assertEqual(shown[-3:], ['--', 'updater', 'run'])


if __name__ == '__main__':
    unittest.main()
