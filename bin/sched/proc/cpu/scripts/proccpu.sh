#!/bin/sh
# Per-thread CPU% snapshot for tagged processes (gofra, nebula).
# Takes two /proc/PID/task/*/stat samples 1s apart, computes utime+
# stime delta per thread, converts to CPU%, emits one line per
# thread plus a per-process summary.
#
# Output:
#   proccpu kind=summary comm=gofra pid=N nthreads=M total_pct=X.X hottest_tid=T hottest_pct=Y.Y
#   proccpu kind=thread  comm=gofra pid=N tid=T pct=X.X cpu=N
#
# `cpu=` in the thread line is the last CPU the thread ran on (field
# 39 of /proc/PID/task/TID/stat). Useful for checking if a hot
# tunReader is bouncing or pinned.

exec timeout -s KILL 10s sh -c '
    HZ=$(getconf CLK_TCK 2>/dev/null || echo 100)
    SECS=1

    snap() {
        proc=$1
        prefix=$2
        for pid in $(pgrep -x "$proc" 2>/dev/null); do
            for tid_path in /proc/$pid/task/*; do
                [ -d "$tid_path" ] || continue
                tid=${tid_path##*/}
                read -r line < "$tid_path/stat" 2>/dev/null || continue
                # /proc/.../stat field 14 (utime) and 15 (stime) are
                # after a "(comm)" group that may contain spaces; we
                # split on the trailing ") " to skip past it.
                rest=${line#*) }
                # rest starts at field 3 (state); fields 14,15 = 12,13
                # of rest after splitting by whitespace.
                set -- $rest
                utime=${12}
                stime=${13}
                cpu=${37}
                printf "%s %s %s %s %s %s\n" "$prefix" "$proc" "$pid" "$tid" "$((utime + stime))" "$cpu"
            done
        done
    }

    {
        snap gofra T0
        snap nebula T0
    } > /tmp/proccpu.before

    sleep $SECS

    {
        snap gofra T1
        snap nebula T1
    } > /tmp/proccpu.after

    awk -v hz="$HZ" -v secs="$SECS" "
        FNR==NR {
            key = \$2 \" \" \$3 \" \" \$4
            ticks[key] = \$5
            next
        }
        {
            key = \$2 \" \" \$3 \" \" \$4
            comm = \$2; pid = \$3; tid = \$4; t1 = \$5; cpu = \$6
            if (key in ticks) {
                d = t1 - ticks[key]
                pct = 100.0 * d / (hz * secs)
                # per-thread line
                printf \"kind=thread comm=%s pid=%s tid=%s pct=%.1f cpu=%s\n\", comm, pid, tid, pct, cpu
                # accumulate per-(comm,pid)
                k = comm \"|\" pid
                tot[k] += pct
                cnt[k] += 1
                if (pct > hottestpct[k]) {
                    hottestpct[k] = pct
                    hottesttid[k] = tid
                }
            }
        }
        END {
            for (k in tot) {
                split(k, a, \"|\")
                printf \"kind=summary comm=%s pid=%s nthreads=%d total_pct=%.1f hottest_tid=%s hottest_pct=%.1f\n\",
                    a[1], a[2], cnt[k], tot[k], hottesttid[k], hottestpct[k]
            }
        }
    " /tmp/proccpu.before /tmp/proccpu.after
' | add_prefix 'proccpu '
