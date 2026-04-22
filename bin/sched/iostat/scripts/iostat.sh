#!/bin/sh
# Lightweight iostat replacement — two snapshots of /proc/diskstats
# 5 seconds apart, delta to r/s, w/s, KB/s, %util, await per real block
# device. Matches `iostat -xk 5 2 | tail` in spirit, minus the sysstat
# dependency.
#
# Fields of /proc/diskstats we use (kernel >=4.18):
#   4 reads_completed   8 writes_completed
#   6 sectors_read     10 sectors_written  (sector = 512B)
#   7 time_reading_ms  11 time_writing_ms
#  13 time_io_ms                    (for %util)
exec timeout -s KILL 30s /bin/sh -c '
tmp=$(mktemp -d) || exit 1
trap "rm -rf $tmp" EXIT

filter="\$3 ~ /^(sd[a-z]+|nvme[0-9]+n[0-9]+)\$/"
awk "$filter" /proc/diskstats > "$tmp/a"
sleep 5
awk "$filter" /proc/diskstats > "$tmp/b"

awk -v win=5 "
FNR==NR { for (i=1;i<=NF;i++) a[\$3,i]=\$i; next }
(\$3 SUBSEP 1) in a {
    r_ops = (\$4  - a[\$3,4])  / win
    w_ops = (\$8  - a[\$3,8])  / win
    r_kbs = (\$6  - a[\$3,6])  / (2*win)
    w_kbs = (\$10 - a[\$3,10]) / (2*win)
    util  = (\$13 - a[\$3,13]) / (win*10)
    ops   = (\$4-a[\$3,4]) + (\$8-a[\$3,8])
    awt   = (ops > 0) ? (((\$7-a[\$3,7]) + (\$11-a[\$3,11])) / ops) : 0
    printf \"%s: r/s=%.1f w/s=%.1f rKB/s=%.1f wKB/s=%.1f util=%.1f%% await=%.1fms\n\",
        \$3, r_ops, w_ops, r_kbs, w_kbs, util, awt
}
" "$tmp/a" "$tmp/b"
' | add_prefix 'iostat '
