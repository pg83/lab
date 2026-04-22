#!/bin/sh
# Per-NIC counters (RX/TX bytes, packets, errors, dropped). `ip -brief
# -s link` prints one row per iface; the interesting columns for
# alerting are err/drop > 0.
exec timeout -s KILL 10s /bin/sh -c '
ip -brief -s link show
' | add_prefix 'netstat '
