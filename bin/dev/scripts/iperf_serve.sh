#!/bin/sh
# 3 iperf2 listeners on ports 5001/5002/5003, bound to this host's
# eth1/eth2/eth3 IPs respectively, each under the matching minio_N
# uid so the uidrange policy rule applies to the server side too.
# Foreground — Ctrl-C stops and reaps.

set -eu

host_base() {
    case "$1" in
        lab1) echo 64 ;;
        lab2) echo 68 ;;
        lab3) echo 72 ;;
        *) echo "unknown host: $1" >&2; exit 3 ;;
    esac
}

H=$(hostname)
BASE=$(host_base "$H")

# Clear any stale listener on our ports. pkill exit 1 = no matches
# (fine); anything else is a real error.
pkill -f 'iperf.*-p 500[1-3]' || [ $? -eq 1 ]

trap 'pkill -f "iperf.*-p 500[1-3]" || [ $? -eq 1 ]' EXIT INT TERM

for i in 1 2 3; do
    IP=10.0.0.$((BASE + i))
    U=$((1012 + i))
    echo "eth$i: uid=$U src=$IP port 500$i"
    su-exec $U iperf -s -p 500$i -B $IP &
done

wait
