#!/bin/sh

# Compare disk health + fsync latency across lab hosts. Targeted at
# the "etcd leader overloaded — slow disk" warnings we keep seeing on
# lab3; this script measures the numbers you need to decide whether
# it's a failing drive, fs-level contention, or a config problem.
#
# Read-only except for a small tempfile used in the fsync probe
# (cleaned up on exit).
#
# Usage:
#   ./disk_probe.sh                 # default hosts lab1 lab2 lab3
#   ./disk_probe.sh lab3            # single host
#
# Assumes key-based ssh as root@<host>.nebula works.

set -eu

if [ "$#" -gt 0 ]; then
    HOSTS="$*"
else
    HOSTS="lab1 lab2 lab3"
fi

for h in $HOSTS; do
    printf '\n====================  %s  ====================\n' "$h"

    ssh -o ConnectTimeout=5 "root@${h}.nebula" '
        set -u

        echo
        echo "--- /home/etcd_private mount ---"
        df -Th /home/etcd_private 2>/dev/null || df -h /home 2>/dev/null

        # /dev/root is a kernel alias; resolve via /proc/self/mountinfo
        # major:minor + /sys/dev/block/<maj:min>/uevent DEVNAME (busybox-safe,
        # no findmnt). Partition name drops trailing digits (and optional
        # "p" for nvme) to get the whole-disk name.
        MAJMIN=$(awk "\$5 == \"/\" {print \$3; exit}" /proc/self/mountinfo)
        ROOTPART=$(. /sys/dev/block/$MAJMIN/uevent 2>/dev/null && echo "/dev/$DEVNAME")
        ROOTDISK=$(echo "${ROOTPART:-/dev/root}" | sed -E "s|p?[0-9]+$||" | sed "s|^/dev/||")
        echo "root_part=${ROOTPART:-?}  root_disk=/dev/$ROOTDISK"

        echo
        echo "--- lsblk (all disks, ROTA=rotational, RM=removable) ---"
        lsblk -o NAME,SIZE,TYPE,ROTA,RM,MOUNTPOINTS 2>/dev/null \
            || lsblk 2>/dev/null \
            || echo "(lsblk unavailable)"

        echo
        echo "--- SMART health (root disk + data disks) ---"
        if command -v smartctl >/dev/null 2>&1; then
            for d in "/dev/$ROOTDISK" /dev/sda /dev/sdb /dev/sdc /dev/sdd; do
                [ -b "$d" ] || continue
                echo "== $d =="
                # 5s timeout — a healthy drive answers immediately; a
                # failing drive with a stuck SATA link can hang smartctl
                # indefinitely (exactly the state this script is
                # supposed to flag). Treat a timeout as its own signal.
                timeout 5 smartctl -H "$d" 2>&1 | grep -E "result|PASSED|FAILED|overall-health" \
                    || echo "  (smartctl -H hung or unavailable — drive possibly degraded)"
                timeout 5 smartctl -A "$d" 2>&1 | grep -iE \
                    "reallocat|pending|uncorrect|wear|percentage|media_wearout|offline_unc|raw_read_error" \
                    | head -8
            done
        else
            echo "(smartctl not installed)"
        fi

        echo
        echo "--- fsync probe: 100 x 4KiB write+fdatasync (wall-clock) ---"
        # Busybox dd does not accept oflag=dsync, so we loop over conv=fdatasync
        # and time the aggregate. fdatasync per op mirrors etcd WAL behaviour.
        # 100 ops, so divide total by 100 for per-op latency.
        T=$(mktemp /tmp/disk_probe.XXXXXX) || T=/tmp/disk_probe.$$
        trap "rm -f $T" EXIT INT TERM

        # Busybox date lacks %N (nanoseconds); /proc/uptime is
        # centisecond-precision wall-clock since boot and is always
        # present. Multiply by 100 to get centiseconds as integer.
        uptime_cs() { awk "{print int(\$1 * 100)}" /proc/uptime; }
        START=$(uptime_cs)
        i=0
        while [ $i -lt 100 ]; do
            dd if=/dev/zero of="$T" bs=4k count=1 conv=fdatasync 2>/dev/null
            i=$((i + 1))
        done
        END=$(uptime_cs)
        TOTAL_MS=$(( (END - START) * 10 ))
        PER_MS=$(( TOTAL_MS / 100 ))
        echo "100 fdatasync ops in ${TOTAL_MS}ms  →  ~${PER_MS}ms/op"
        echo "(etcd_disk_wal_fsync p99 target: <10ms; >100ms = alarm)"
        rm -f "$T"

        echo
        echo "--- dmesg: disk/IO errors (ANY disk, last 30 matching) ---"
        # dmesg in stalix may require root (it does here — we ssh as root).
        # Some builds of dmesg do not support -T; drop the flag.
        DMESG=$(dmesg 2>/dev/null) || DMESG=""
        if [ -z "$DMESG" ]; then
            echo "(dmesg empty or unavailable)"
        else
            echo "$DMESG" | grep -iE "ata[0-9]|nvme|sector|i/o error|medium error|blk_update|xfs.*error|ext4.*error|btrfs.*error|reset|hard resetting|scsi.*error" \
                | tail -30 \
                || echo "(no matching disk errors in dmesg)"
        fi

        echo
        echo "--- iostat snapshot (1s x 3) ---"
        if command -v iostat >/dev/null 2>&1; then
            # Minimal busybox iostat: just -d (device) and 1 3 for interval x count.
            iostat -d 1 3 2>&1 | tail -n +3
        else
            echo "(iostat not installed)"
        fi

        echo
        echo "--- /proc/diskstats for /dev/$ROOTDISK ---"
        grep -w "$ROOTDISK" /proc/diskstats 2>/dev/null | head -3 \
            || echo "(no match)"

        echo
    '
done
