#!/usr/bin/env python3

"""
Live per-device await/util/iops from /proc/diskstats.

BusyBox iostat has no `-x` flag, so the extended stats you actually
need (write latency, queue depth, %util) aren't available. This
script reads /proc/diskstats directly once per interval and prints
the derived metrics — same columns as `iostat -xdm` on glibc.

Targeted at debugging slow etcd wal_fsync on the cluster's rootfs
disk. Healthy SATA SSD: w_await < 5 ms even under load. USB-bridged
SSD with broken sync passthrough: 20–100 ms under modest IOPS.
"""

import argparse
import sys
import time


STATS = (
    'rd_ios', 'rd_merges', 'rd_sectors', 'rd_ms',
    'wr_ios', 'wr_merges', 'wr_sectors', 'wr_ms',
    'in_flight', 'io_ms', 'weighted_io_ms',
)


def read_stats(device):
    with open('/proc/diskstats') as f:
        for line in f:
            parts = line.split()

            if len(parts) < 14 or parts[2] != device:
                continue

            return dict(zip(STATS, (int(p) for p in parts[3:3 + len(STATS)])))

    raise SystemExit(f'device {device!r} not found in /proc/diskstats')


def main():
    ap = argparse.ArgumentParser(description='Live iostat-x for BusyBox hosts.')
    ap.add_argument('-d', '--device', default='sdd', help='block device name (default: sdd)')
    ap.add_argument('-n', '--count', type=int, default=30, help='number of samples (default: 30)')
    ap.add_argument('-i', '--interval', type=float, default=1.0, help='interval seconds (default: 1.0)')
    args = ap.parse_args()

    prev = read_stats(args.device)
    prev_t = time.time()

    hdr = f'{"time":>8} {"r/s":>6} {"w/s":>6} {"rMB/s":>7} {"wMB/s":>7} {"r_await":>8} {"w_await":>8} {"aqu-sz":>7} {"%util":>6}'
    print(hdr)

    for _ in range(args.count):
        time.sleep(args.interval)
        cur = read_stats(args.device)
        cur_t = time.time()
        dt = cur_t - prev_t

        rdd = max(cur['rd_ios'] - prev['rd_ios'], 0)
        wrd = max(cur['wr_ios'] - prev['wr_ios'], 0)
        rds = max(cur['rd_sectors'] - prev['rd_sectors'], 0)
        wrs = max(cur['wr_sectors'] - prev['wr_sectors'], 0)
        rdm = max(cur['rd_ms'] - prev['rd_ms'], 0)
        wrm = max(cur['wr_ms'] - prev['wr_ms'], 0)
        iom = max(cur['io_ms'] - prev['io_ms'], 0)
        wim = max(cur['weighted_io_ms'] - prev['weighted_io_ms'], 0)

        r_await = (rdm / rdd) if rdd else 0.0
        w_await = (wrm / wrd) if wrd else 0.0
        aqu_sz = wim / (dt * 1000)
        util = (iom / (dt * 1000)) * 100

        print(f'{time.strftime("%H:%M:%S"):>8} '
              f'{int(rdd / dt):>6} {int(wrd / dt):>6} '
              f'{rds * 512 / dt / 1e6:>7.2f} {wrs * 512 / dt / 1e6:>7.2f} '
              f'{r_await:>8.2f} {w_await:>8.2f} '
              f'{aqu_sz:>7.2f} {util:>6.1f}')

        sys.stdout.flush()
        prev, prev_t = cur, cur_t


if __name__ == '__main__':
    main()
