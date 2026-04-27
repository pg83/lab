#!/bin/sh

# Survey + tune NIC parameters across the lab. For each ethN on each
# host: driver, link speed, ring buffer size, coalescing settings,
# flow control, accumulated drop counters, busiest RX-IRQ queues.
#
# Default: read-only inspection. With --apply: bumps RX/TX ring to
# max and disables adaptive coalescing (best-effort; ignores
# unsupported parameters per driver).
#
# Usage:
#   nic_tune.sh                    inspect lab1 lab2 lab3
#   nic_tune.sh lab2               inspect just lab2
#   nic_tune.sh --apply lab2 lab3  inspect AND bump rings on those
#
# Assumes root@<host>.nebula ssh works (key-based).

set -eu

APPLY=0
HOSTS=""

for arg in "$@"; do
    case "$arg" in
        --apply) APPLY=1 ;;
        -h|--help)
            sed -n '3,17p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) HOSTS="$HOSTS $arg" ;;
    esac
done

[ -z "$HOSTS" ] && HOSTS="lab1 lab2 lab3"

hdr() {
    printf '\n==== %s ====\n' "$*"
}

for h in $HOSTS; do
    hdr "$h"

    ssh -o BatchMode=yes -o ConnectTimeout=5 "root@$h.nebula" \
        APPLY="$APPLY" 'sh -s' <<'REMOTE' || echo "  ssh $h failed"
set -u

# Sum drop counters from ethtool -S, focused on what actually matters
# for "kernel-side ring overflow" diagnosis.
drops_summary() {
    iface=$1
    ethtool -S "$iface" 2>/dev/null | awk '
        /rx_dropped|rx_missed|rx_no_buffer|rx_fifo|tx_dropped|tx_fifo/ {
            gsub(/[: \t]+/, "=", $0)
            n = split($0, parts, "=")
            if (parts[n] != "0") print "    " parts[n-1] "=" parts[n]
        }
    '
}

# Busiest RX-TxRx queues by total interrupt count.
top_busy_queues() {
    iface=$1
    awk -v ifx="$iface" '
        $NF ~ ifx"-TxRx-" {
            sum=0
            for (i=2; i<=NF-3; i++) sum += $i
            print sum, $NF
        }
    ' /proc/interrupts | sort -rn | head -5 | awk '{printf "    %s = %s irqs\n", $2, $1}'
}

# ethtool -G on stalix busybox can't take rx 0 — skip 0/missing fields.
ring_max_field() {
    out=$1
    field=$2
    awk -v f="$field:" '$1==f {print $2; exit}' "$out"
}

bump_rings() {
    iface=$1
    out=$(ethtool -g "$iface" 2>/dev/null) || return 0

    # ethtool -g output has two passes (max, then current) without
    # section headers. Take 1st RX/TX as max, 2nd as current.
    rx_max=$(echo "$out" | awk '/^RX:/{print $2; exit}')
    tx_max=$(echo "$out" | awk '/^TX:/{print $2; exit}')

    if [ -z "$rx_max" ] || [ "$rx_max" = "n/a" ]; then
        return 0
    fi

    args="rx $rx_max"
    [ -n "$tx_max" ] && [ "$tx_max" != "n/a" ] && args="$args tx $tx_max"

    if ethtool -G "$iface" $args 2>&1; then
        echo "    ring → rx=$rx_max tx=${tx_max:-n/a} OK"
    else
        echo "    ring tune failed"
    fi
}

tune_coalesce() {
    iface=$1

    # Best-effort: ixgbe accepts adaptive-rx off + rx-usecs N; igb has
    # different supported subset. Try them one by one so a partial
    # failure doesn't drop the rest.
    ethtool -C "$iface" adaptive-rx off 2>/dev/null && echo "    adaptive-rx → off" || true
    ethtool -C "$iface" rx-usecs 1 2>/dev/null && echo "    rx-usecs → 1" || true
}

for iface in /sys/class/net/eth*; do
    [ -d "$iface" ] || continue
    i=${iface##*/}

    echo
    echo "-- $i --"

    drv=$(ethtool -i "$i" 2>/dev/null | awk '/^driver:/{print $2}')
    fw=$(ethtool -i "$i" 2>/dev/null | awk '/^firmware-version:/{$1=""; print}' | sed 's/^ //')
    speed=$(ethtool "$i" 2>/dev/null | awk '/Speed:/{print $2}')
    duplex=$(ethtool "$i" 2>/dev/null | awk '/Duplex:/{print $2}')
    link=$(ethtool "$i" 2>/dev/null | awk '/Link detected:/{print $3}')

    printf '  driver=%s  fw=%s  link=%s  %s/%s\n' "$drv" "$fw" "$link" "$speed" "$duplex"

    # Ring buffer — ethtool -g prints two passes (max then current)
    # without section headers, so we take the 1st RX/TX as max and
    # the 2nd as current.
    g=$(ethtool -g "$i" 2>/dev/null) || g=""
    if [ -n "$g" ]; then
        rx_max=$(echo "$g" | awk '/^RX:/{print $2; if(++c==1) exit}')
        tx_max=$(echo "$g" | awk '/^TX:/{print $2; if(++c==1) exit}')
        rx_cur=$(echo "$g" | awk '/^RX:/{c++; if(c==2){print $2; exit}}')
        tx_cur=$(echo "$g" | awk '/^TX:/{c++; if(c==2){print $2; exit}}')
        printf '  ring: rx=%s/%s  tx=%s/%s\n' "${rx_cur:-?}" "${rx_max:-?}" "${tx_cur:-?}" "${tx_max:-?}"
    fi

    # Coalescing.
    c=$(ethtool -c "$i" 2>/dev/null) || c=""
    if [ -n "$c" ]; then
        adaptive_rx=$(echo "$c" | awk '/Adaptive RX:/{print $3}')
        rx_usecs=$(echo "$c" | awk '/^rx-usecs:/{print $2}')
        rx_frames=$(echo "$c" | awk '/^rx-frames:/{print $2}')
        printf '  coalesce: adaptive-rx=%s rx-usecs=%s rx-frames=%s\n' \
            "${adaptive_rx:-?}" "${rx_usecs:-?}" "${rx_frames:-?}"
    fi

    # Flow control.
    a=$(ethtool -a "$i" 2>/dev/null) || a=""
    if [ -n "$a" ]; then
        fc_rx=$(echo "$a" | awk '/^RX:/{print $2}')
        fc_tx=$(echo "$a" | awk '/^TX:/{print $2}')
        fc_aut=$(echo "$a" | awk '/Autonegotiate:/{print $2}')
        printf '  flow-ctl: rx=%s tx=%s autoneg=%s\n' "${fc_rx:-?}" "${fc_tx:-?}" "${fc_aut:-?}"
    fi

    # Drop counters.
    d=$(drops_summary "$i")
    if [ -n "$d" ]; then
        echo "  drops:"
        echo "$d"
    else
        echo "  drops: 0"
    fi

    # Top busy queues — only meaningful on multi-queue NICs.
    qs=$(top_busy_queues "$i")
    if [ -n "$qs" ]; then
        echo "  busiest IRQ queues:"
        echo "$qs"
    fi

    # Apply tuning if requested.
    if [ "${APPLY:-0}" = "1" ]; then
        echo "  applying tune:"
        bump_rings "$i"
        tune_coalesce "$i"
    fi
done

# /proc/net/snmp UDP errors — global, but useful diagnostic.
echo
echo "-- /proc/net/snmp UDP --"
awk '/^Udp:/ {if (header) {n=split(header, h); split($0, v); for (i=2; i<=n; i++) printf "  %s=%s\n", h[i], v[i]; exit} else header=$0}' /proc/net/snmp

# TUN device counters — what we really want for "is gofra dropping
# at the TUN qdisc?". Busybox `ip` output is sparse; the full one
# lives in /ix/realm/ip/bin/ip via bin/ip/route2. Print -s -s twice
# to get extended counters including dropped/overrun.
echo
echo "-- gofra0 (TUN) --"
IPCMD=/ix/realm/ip/bin/ip
[ -x "$IPCMD" ] || IPCMD=ip
"$IPCMD" -s -s link show gofra0 2>/dev/null || echo "  gofra0 not present"

# txqueuelen on gofra0 caps the qdisc depth between kernel and the
# tunReader goroutine. Default 500-1000 = ~1.7-3ms of buffering at
# 290K pps; bumping to 10000 gives ~30ms headroom for bursts.
if [ "${APPLY:-0}" = "1" ] && "$IPCMD" link show gofra0 >/dev/null 2>&1; then
    echo "  applying tune:"
    if "$IPCMD" link set gofra0 txqueuelen 10000 2>&1; then
        echo "    txqueuelen → 10000 OK"
    else
        echo "    txqueuelen tune failed"
    fi
fi

REMOTE
done
