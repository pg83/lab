"""SMART failures must not become healthy zeros or retain stale readings."""

import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('smart', ROOT / 'bin/sched/smart/scripts/smart.py')
smart = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smart)


def disk(serial='disk-one', pending=0, passed=True):
    return {'serial_number': serial, 'model_name': 'test HDD', 'rotation_rate': 5400,
            'smart_status': {'passed': passed}, 'temperature': {'current': 0},
            'ata_smart_attributes': {'table': [
                {'id': 197, 'name': 'Current_Pending_Sector', 'raw': {'value': pending}},
            ]}}


class SmartTests(unittest.TestCase):
    def render(self, data, code=0):
        metrics = smart.Metrics()
        with mock.patch('builtins.print') as log:
            smart.device_metrics(metrics, '/dev/sdb', data, code)
        return '\n'.join(metrics.lines), log.call_args.args[0]

    def test_zero_is_not_unknown_and_absent_is_not_zero(self):
        text, line = self.render(disk())
        self.assertIn('PENDING=0', line)
        self.assertIn('TEMP=0', line)
        self.assertIn('REALLOC=?', line)
        self.assertNotIn('attribute_id="5"', text)
        self.assertIn('attribute_id="197"', text)

    def test_health_failure_and_old_errors_keep_measurements(self):
        text, line = self.render(disk(pending=32, passed=False), 8 | 64)
        self.assertIn('PENDING=32', line)
        self.assertIn('HEALTH=FAILED', line)
        samples = [s for s in text.splitlines() if not s.startswith('#')]
        self.assertTrue(next(s for s in samples if s.startswith('smart_device_scrape_success')).endswith(' 1'))
        self.assertTrue(next(s for s in samples if s.startswith('smart_device_health_passed')).endswith(' 0'))

    def test_failed_poll_replaces_stale_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'smart.prom'
            old, _ = self.render(disk(pending=16))
            smart.publish(path, old.splitlines())
            failed, _ = self.render(disk(pending=0), 2)
            smart.publish(path, failed.splitlines())
            self.assertNotIn('smart_ata_attribute_raw_value', path.read_text())
            self.assertNotIn('smart_device_health_passed', path.read_text())
            self.assertIn('smart_device_scrape_success', path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_replacement_disk_has_distinct_series(self):
        first, _ = self.render(disk(serial='first'))
        second, _ = self.render(disk(serial='second'))
        self.assertIn('serial="first"', first)
        self.assertIn('serial="second"', second)
        self.assertNotIn('serial="first"', second)

    def test_missing_serial_does_not_publish_unidentified_health(self):
        text, _ = self.render(disk(serial=''))
        self.assertNotIn('smart_device_health_passed', text)

    def test_timeout_does_not_abort_collection(self):
        with mock.patch.object(smart.subprocess, 'run', side_effect=smart.subprocess.TimeoutExpired('smartctl', 15)):
            self.assertEqual(smart.read_smart('/dev/sdb'), ({}, 2))

    def test_labels_are_escaped(self):
        text, _ = self.render(disk(serial='a"b\\c\nd'))
        self.assertIn('serial="a\\"b\\\\c\\nd"', text)


if __name__ == '__main__':
    unittest.main()
