#!/bin/sh
# `xfs_info <mount>` for every XFS mount — sector/block size, log geometry,
# allocation group layout, mount options. Mostly static; useful once
# after provisioning and on config drift (label swap, remount without
# nobarrier, etc.).
exec timeout -s KILL 15s /bin/sh -c '
awk "\$3==\"xfs\" {print \$2}" /proc/mounts | sort -u | while read mnt; do
    (xfs_info "$mnt" 2>&1 ; echo "---") | add_prefix "xfs $mnt: "
done
' | add_prefix 'xfsinfo '
