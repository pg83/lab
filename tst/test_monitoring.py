"""Check the monitoring config serialized into the actual service runners."""

import base64
import io
import pathlib
import re
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'lab'))

import cg


class MonitoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = cg.do((ROOT / 'lab' / 'cg.py').read_text())

    def service(self, host, name):
        for line in self.config['by_host'][host]['extra'].splitlines():
            if line.startswith('bin/run/sh(') and f'srv_dir={name},' in line:
                encoded = re.search(r'runsh_script=([^,]+)', line)[1]
                runner = base64.b64decode(encoded).decode()
                payload = base64.b64decode(runner.split()[2])
                return cg._Unpickler(io.BytesIO(payload)).load()['srv']
        self.fail(f'no runner for {host}/{name}')

    def test_collectors_monitor_themselves_and_active_services(self):
        for host in ('lab1', 'lab2', 'lab3'):
            with self.subTest(host=host):
                collector = self.service(host, 'collector')
                jobs = collector.config()['scrape_configs']
                names = [job['job_name'] for job in jobs]
                self.assertEqual(len(names), len(set(names)))
                self.assertIn('collector', names)
                self.assertIn('promtail', names)
                self.assertIn('s3_front', names)
                self.assertTrue(set(names).isdisjoint(self.config['by_host'][host]['disabled']))
                own = next(job for job in jobs if job['job_name'] == 'collector')
                self.assertEqual(own['static_configs'][0]['targets'],
                                 [f'{collector.listen}:{collector.port}'])

    def test_grafana_services_exclude_retired_minio(self):
        for host in ('lab1', 'lab2', 'lab3'):
            with self.subTest(host=host):
                services = self.service(host, 'grafana').services
                self.assertNotIn('minio', services)
                self.assertNotIn('minio_console', services)
                self.assertIn('s3_front', services)


if __name__ == '__main__':
    unittest.main()
