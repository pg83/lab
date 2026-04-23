#!/bin/sh
# Fire 3 parallel iperf2 streams from this host toward REMOTE_HOST,
# one per eth1/eth2/eth3 pair, each under the matching minio_N uid
# so both ends' uidrange policy rules fire. Aggregate saturation
# (3 × ~gigabit) proves the multi-home stack end-to-end.
#
# Usage: iperf_shot REMOTE_HOST [DURATION_SECS]
#   REMOTE_HOST ∈ {lab1, lab2, lab3}, default duration 30s.
# Per-stream logs land in $PWD as iperf-eth{1,2,3}-<self>-to-<remote>.log.

set -eu

REMOTE=${1:?usage: iperf_shot REMOTE_HOST [DUR]}
DUR=${2:-30}

host_base() {
    case "$1" in
        lab1) echo 64 ;;
        lab2) echo 68 ;;
        lab3) echo 72 ;;
        *) echo "unknown host: $1" >&2; exit 3 ;;
    esac
}

H=$(hostname)
CBASE=$(host_base "$H")
SBASE=$(host_base "$REMOTE")

for i in 1 2 3; do
    CLI_IP=10.0.0.$((CBASE + i))
    SRV_IP=10.0.0.$((SBASE + i))
    U=$((1012 + i))
    LOG="./iperf-eth${i}-${H}-to-${REMOTE}.log"
    echo "eth$i: uid=$U src=$CLI_IP → dst=$SRV_IP ($LOG)"
    su-exec $U iperf -c $SRV_IP -p 500$i -B $CLI_IP -t $DUR -i 5 > "$LOG" 2>&1 &
done

wait

echo
echo "=== summary ==="
TOTAL=0
for i in 1 2 3; do
    LOG="./iperf-eth${i}-${H}-to-${REMOTE}.log"
    line=$(grep -E 'Mbits/sec|Gbits/sec' "$LOG" | tail -1)
    echo "  eth${i}: $line"
    mbps=$(echo "$line" | awk '
        /Gbits\/sec/ { for (i=1; i<=NF; i++) if ($i ~ /^[0-9.]+$/) v=$i; print int(v*1000); exit }
        /Mbits\/sec/ { for (i=1; i<=NF; i++) if ($i ~ /^[0-9.]+$/) v=$i; print int(v); exit }
    ')
    TOTAL=$((TOTAL + ${mbps:-0}))
done
echo "  ----"
echo "  total: ${TOTAL} Mbits/sec"
