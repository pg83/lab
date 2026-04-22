#!/bin/sh
# Filesystem fill (df-size) and inode fill (df-inode), one line per
# mount, virtual filesystems filtered out. Watch for use% creeping
# past ~85% — XFS and MinIO don't like a full drive.
exec timeout -s KILL 10s /bin/sh -c '
skip="^(tmpfs|devtmpfs|proc|sysfs|cgroup2?|overlay|squashfs|ramfs|pstore|bpf|tracefs|debugfs|autofs|mqueue|fusectl|configfs|securityfs|nsfs|hugetlbfs)$"

df -P -T -B M 2>/dev/null | awk -v skip="$skip" "NR>1 && \$2 !~ skip" | add_prefix "df-size: "
df -P -T -i   2>/dev/null | awk -v skip="$skip" "NR>1 && \$2 !~ skip" | add_prefix "df-inode: "
' | add_prefix 'df '
