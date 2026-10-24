#!/usr/bin/env python3
"""Read SMART once per scheduler cycle; atomically publish a textfile snapshot."""

import argparse
import json
import math
import os
import pathlib
import re
import subprocess
import tempfile
import time


OUTPUT = '/var/run/node_exporter/textfile/smart.prom'
ATTRIBUTES = {5, 197, 198, 199}


class Metrics:
    def __init__(self):
        self.lines = []
        self.names = set()

    def add(self, name, help_text, value, labels=None):
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return
        if name not in self.names:
            self.lines.extend([f'# HELP {name} {help_text}', f'# TYPE {name} gauge'])
            self.names.add(name)
        # Prometheus label escaping differs from JSON for non-ASCII/control chars.
        def quote(v):
            return str(v).replace('\\', '\\\\').replace('\n', '\\n').replace('"', '\\"')
        fields = ','.join(f'{k}="{quote(v)}"' for k, v in sorted((labels or {}).items()))
        suffix = '{' + fields + '}' if fields else ''
        self.lines.append(f'{name}{suffix} {int(value) if isinstance(value, bool) else value}')


def read_smart(device):
    try:
        proc = subprocess.run(['smartctl', '-j', '-i', '-H', '-A', device],
                              capture_output=True, text=True, timeout=15)
        data = json.loads(proc.stdout)
        # Bits 0..2 are command/read failures. Bits 3..7 describe disk health
        # or historical errors and must not suppress usable SMART readings.
        return data, proc.returncode
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {}, 2


def device_metrics(metrics, device, data, returncode):
    serial = data.get('serial_number', '')
    rotation = data.get('rotation_rate')
    protocol = data.get('device', {}).get('protocol', '')
    kind = ('nvme' if protocol == 'NVMe' else
            'hdd' if isinstance(rotation, int) and rotation > 0 else
            'ssd' if rotation == 0 else 'unknown')
    labels = {'device': pathlib.Path(device).name, 'serial': serial,
              'model': data.get('model_name', data.get('product', '')), 'disk_type': kind}
    attrs = {a['id']: a for a in data.get('ata_smart_attributes', {}).get('table', [])}
    health = data.get('smart_status', {}).get('passed')
    nvme = data.get('nvme_smart_health_information_log', {})
    success = bool(serial and (health is not None or attrs or nvme) and not (returncode & 7))
    metrics.add('smart_device_info', 'Disk identity reported by smartctl.', 1, labels)
    metrics.add('smart_device_scrape_success', 'SMART poll produced usable readings and a serial number.', success, labels)
    if not success:
        print(f'smart {labels["device"]}: HEALTH=? TEMP=? REALLOC=? PENDING=? OFFLINE_UNC=? SERIAL={serial or "?"} SCRAPE=FAILED', flush=True)
        return

    metrics.add('smart_device_health_passed', 'Device overall SMART assessment: 1 passed, 0 failed.', health, labels)
    temperature = data.get('temperature', {}).get('current')
    metrics.add('smart_device_temperature_celsius', 'Current device temperature.', temperature, labels)
    hours = data.get('power_on_time', {}).get('hours')
    metrics.add('smart_device_power_on_seconds', 'Power-on time reported by the device.',
                hours * 3600 if isinstance(hours, (int, float)) else None, labels)
    for aid in sorted(ATTRIBUTES & attrs.keys()):
        attr = attrs[aid]
        metrics.add('smart_ata_attribute_raw_value', 'Raw ATA attribute; interpretation is model-specific, especially on SSDs.',
                    attr.get('raw', {}).get('value'),
                    {**labels, 'attribute_id': str(aid), 'attribute_name': attr['name']})
    for key in ('critical_warning', 'media_errors', 'percentage_used', 'available_spare'):
        metrics.add('smart_nvme_' + key, 'NVMe SMART ' + key.replace('_', ' ') + '.', nvme.get(key), labels)

    def raw(aid):
        return attrs.get(aid, {}).get('raw', {}).get('value', '?')
    state = '?' if health is None else 'PASSED' if health else 'FAILED'
    temp = '?' if temperature is None else temperature
    print(f'smart {labels["device"]}: HEALTH={state} TEMP={temp} REALLOC={raw(5)} PENDING={raw(197)} OFFLINE_UNC={raw(198)} SERIAL={serial}', flush=True)


def publish(path, lines):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    # A concurrent node_exporter scrape sees either the complete old snapshot
    # or the complete new one. Failed polls replace old values with failure.
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            os.fchmod(f.fileno(), 0o644)
            f.write('\n'.join(lines) + '\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=OUTPUT)
    args = parser.parse_args()
    started = time.monotonic()
    devices = sorted(p.name for p in pathlib.Path('/sys/class/block').iterdir()
                     if re.fullmatch(r'sd[a-z]+|nvme\d+n\d+', p.name))
    metrics = Metrics()
    for name in devices:
        device = '/dev/' + name
        device_metrics(metrics, device, *read_smart(device))
    metrics.add('smart_collect_timestamp_seconds', 'Unix time of the last completed SMART collection.', time.time())
    metrics.add('smart_collect_duration_seconds', 'Duration of the last SMART collection.', time.monotonic() - started)
    metrics.add('smart_collect_devices', 'Number of discovered disks in the last collection.', len(devices))
    publish(args.output, metrics.lines)


if __name__ == '__main__':
    main()
