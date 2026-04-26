#!/bin/sh
# Per-NIC counters (RX/TX bytes, packets, errors, dropped). The
# interesting columns for alerting are err/drop > 0.
#
# Reads /proc/net/dev directly. We tried `ip -brief -s link show`
# but stalix /bin/ip is busybox, which doesn't grok -brief / -s /
# `link show` and just prints help to stdout. /proc/net/dev is
# always there, awk-parsable, and stable across kernel versions.
exec timeout -s KILL 10s awk '
    NR > 2 {
        gsub(/:/, "", $1)

        printf "iface=%s rx_bytes=%s rx_pkt=%s rx_err=%s rx_drop=%s tx_bytes=%s tx_pkt=%s tx_err=%s tx_drop=%s\n", \
            $1, $2, $3, $4, $5, $10, $11, $12, $13
    }
' /proc/net/dev | add_prefix 'netstat '
