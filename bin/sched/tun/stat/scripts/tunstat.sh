#!/bin/sh
# Per-TUN-device counters read directly from sysfs, including the
# error/drop fields omitted by busybox `ip`.
#
# Output format (one line per direction per device):
#   tunstat dev=gofra0 dir=rx bytes=N packets=N errors=N dropped=N missed=N mcast=N
#   tunstat dev=gofra0 dir=tx bytes=N packets=N errors=N dropped=N carrier=N collsns=N

exec timeout -s KILL 10s sh -c '
    net_stat() {
        stat_file="/sys/class/net/$1/statistics/$2"
        if [ -r "$stat_file" ]; then
            read -r stat_value < "$stat_file"
            printf "%s" "$stat_value"
        else
            printf "0"
        fi
    }

    for dev in gofra0 nebula1; do
        [ -d "/sys/class/net/$dev" ] || continue

        printf "dev=%s dir=rx bytes=%s packets=%s errors=%s dropped=%s missed=%s mcast=%s\n" \
            "$dev" \
            "$(net_stat "$dev" rx_bytes)" \
            "$(net_stat "$dev" rx_packets)" \
            "$(net_stat "$dev" rx_errors)" \
            "$(net_stat "$dev" rx_dropped)" \
            "$(net_stat "$dev" rx_missed_errors)" \
            "$(net_stat "$dev" multicast)"
        printf "dev=%s dir=tx bytes=%s packets=%s errors=%s dropped=%s carrier=%s collsns=%s\n" \
            "$dev" \
            "$(net_stat "$dev" tx_bytes)" \
            "$(net_stat "$dev" tx_packets)" \
            "$(net_stat "$dev" tx_errors)" \
            "$(net_stat "$dev" tx_dropped)" \
            "$(net_stat "$dev" tx_carrier_errors)" \
            "$(net_stat "$dev" collisions)"
    done
' | add_prefix 'tunstat '
