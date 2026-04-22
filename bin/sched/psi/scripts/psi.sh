#!/bin/sh
# /proc/pressure/{io,memory,cpu} — PSI counters. Two lines per subsys
# (some / full), no timestamps; avg10 / avg60 / avg300 are straight grep
# targets, e.g.
#     logcli query '{service="sched100"} |~ "psi io some.*avg60=[1-9]"'
exec timeout -s KILL 10s /bin/sh -c '
for sub in io memory cpu; do
    [ -r /proc/pressure/$sub ] || continue
    awk -v s="$sub" "{print s, \$0}" /proc/pressure/$sub
done
' | add_prefix 'psi '
