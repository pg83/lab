#!/bin/sh
# Per-NIC ethtool counters, filtered to the loss-flavoured fields.
#
# /proc/net/dev (covered by bin/sched/net/stat) only gives the
# IP-layer rx_drop/tx_drop pair. ethtool -S exposes the driver and
# hardware-level ones we actually need to spot stripe-burst NIC
# overflows: rx_no_buffer_count, rx_missed_errors, rx_fifo_errors,
# rx_long_length_errors, etc. The exact field names are driver-
# specific so we just regex broadly and let the consumer filter.
exec timeout -s KILL 10s sh -c '
    for iface in /sys/class/net/eth*; do
        [ -d "$iface" ] || continue
        i=${iface##*/}

        ethtool -S "$i" 2>/dev/null | awk -v i=$i "
            /drop|fifo|missed|over|rx_no_buffer|rx_long_length|crc_err|err_count/ {
                gsub(/^[ \\t]+/, \"\")
                gsub(/:[ \\t]+/, \"=\")
                print \"iface=\" i \" \" \$0
            }
        "
    done
' | add_prefix 'ethstat '
