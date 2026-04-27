#!/bin/sh
# Per-TUN-device counters via the full iproute2 binary
# (/ix/realm/ip/bin/ip) — busybox `ip` doesn't print errors / dropped
# / overrun fields, which are the entire reason we want this in
# sched10. The `-s -s` flag prints "extended" stats including
# ALIGNERR/MISSED that the driver tracks below /proc/net/dev.
#
# Output format (one line per direction per device):
#   tunstat dev=gofra0 dir=rx bytes=N packets=N errors=N dropped=N missed=N mcast=N
#   tunstat dev=gofra0 dir=tx bytes=N packets=N errors=N dropped=N carrier=N collsns=N

exec timeout -s KILL 10s sh -c '
    IPCMD=/ix/realm/ip/bin/ip
    [ -x "$IPCMD" ] || IPCMD=ip

    for dev in gofra0 nebula1; do
        [ -d "/sys/class/net/$dev" ] || continue

        "$IPCMD" -s -s link show "$dev" 2>/dev/null | awk -v dev="$dev" "
            /RX:/ { rx=1; tx=0; next }
            /TX:/ { tx=1; rx=0; next }
            rx && /^[[:space:]]*[0-9]/ && nrx==0 {
                printf \"dev=%s dir=rx bytes=%s packets=%s errors=%s dropped=%s missed=%s mcast=%s\n\", dev, \$1, \$2, \$3, \$4, \$5, \$6
                nrx=1
            }
            tx && /^[[:space:]]*[0-9]/ && ntx==0 {
                printf \"dev=%s dir=tx bytes=%s packets=%s errors=%s dropped=%s carrier=%s collsns=%s\n\", dev, \$1, \$2, \$3, \$4, \$5, \$6
                ntx=1
            }
        "
    done
' | add_prefix 'tunstat '
