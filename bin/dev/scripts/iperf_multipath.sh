#!/bin/sh

# Multi-NIC iperf harness. Drives 3 parallel TCP streams between
# CLIENT host and SERVER host, one per (ethN ↔ ethN) pair. Each
# client runs as the matching minio_N user so the uid-based policy
# rule fires — same path real minio peer-grid traffic takes.
#
# If the 3 streams saturate simultaneously at ~gigabit each, the
# multi-home stack (pin_minio_nic policy routing + arp_strict ARP
# determinism) is healthy end-to-end.
#
# Usage:
#   ./iperf_multipath.sh [CLIENT] [SERVER] [DURATION]
# Defaults: lab1 → lab2, 30s.
#
# Per-stream logs land in $PWD:
#   iperf-eth1-<client>-to-<server>.log
#   iperf-eth2-<client>-to-<server>.log
#   iperf-eth3-<client>-to-<server>.log

set -eu

CLIENT=${1:-lab1}
SERVER=${2:-lab2}
DUR=${3:-30}

host_base() {
    case "$1" in
        lab1) echo 64 ;;
        lab2) echo 68 ;;
        lab3) echo 72 ;;
        *) echo "unknown host: $1" >&2; exit 3 ;;
    esac
}

CBASE=$(host_base "$CLIENT")
SBASE=$(host_base "$SERVER")

echo "=== starting servers on $SERVER (ports 5001-5003, bound to eth1/2/3) ==="
ssh -o ConnectTimeout=5 "root@${SERVER}.nebula" "
    set -u
    pkill -f 'iperf.*-p 500[1-3]' 2>/dev/null || true
    sleep 1
    for i in 1 2 3; do
        IP=10.0.0.\$((${SBASE} + i))
        iperf -s -p 500\$i -B \$IP -D
    done
    sleep 1
    echo 'listeners:'
    ss -tlnp 2>/dev/null | awk '/iperf/ {print \"  \" \$4}'
"

echo
echo "=== clients on $CLIENT, ${DUR}s, parallel, each su-exec minio_N ==="
for i in 1 2 3; do
    CLI_IP=10.0.0.$((CBASE + i))
    SRV_IP=10.0.0.$((SBASE + i))
    U=$((1012 + i))
    LOG="./iperf-eth${i}-${CLIENT}-to-${SERVER}.log"
    echo "  eth$i: uid=$U src=$CLI_IP → dst=$SRV_IP  (→ $LOG)"
    ssh -o ConnectTimeout=5 "root@${CLIENT}.nebula" \
        "su-exec $U iperf -c $SRV_IP -p 500$i -B $CLI_IP -t $DUR -i 5" \
        > "$LOG" 2>&1 &
done

wait

echo
echo "=== summary ==="
TOTAL_MBPS=0
for i in 1 2 3; do
    LOG="./iperf-eth${i}-${CLIENT}-to-${SERVER}.log"
    # Last "sum" line — iperf2 always prints a 0.00-<DUR> summary at the end.
    line=$(grep -E 'Mbits/sec|Gbits/sec' "$LOG" | tail -1)
    echo "  eth${i}: $line"
    # Extract the Mbits/sec number for a total (rough; Gbits treated x1000).
    mbps=$(echo "$line" | awk '
        /Gbits\/sec/ { for (i=1; i<=NF; i++) if ($i ~ /^[0-9.]+$/) val=$i; print int(val * 1000); exit }
        /Mbits\/sec/ { for (i=1; i<=NF; i++) if ($i ~ /^[0-9.]+$/) val=$i; print int(val); exit }
    ')
    TOTAL_MBPS=$((TOTAL_MBPS + ${mbps:-0}))
done
echo "  ----"
echo "  total: ${TOTAL_MBPS} Mbits/sec"

echo
echo "=== stopping servers on $SERVER ==="
ssh "root@${SERVER}.nebula" "pkill -f 'iperf.*-p 500[1-3]' 2>/dev/null || true"
