#!/bin/sh
# lab1: use free space on four existing XFS filesystems, without formatting.
# Run with --check for inspection only; without arguments to mount/create dirs.
set -eu
[ "$(hostname)" = lab1 ] || { echo 'This layout is only for lab1' >&2; exit 1; }
mode=${1:-mount}
case "$mode" in mount|--check) ;; *) exit 2 ;; esac

volumes='6b194f91-10fc-4ad6-9f30-21581c641d56 seagate-a
2a39d5d3-80be-4b9c-bb99-0924d597c9e1 seagate-b
7b654717-6493-4534-90b5-c947fa8b7045 hgst-a
2617f25c-d4f5-4f38-acfe-c1cdd5250aed hgst-b'

preflight() {
    printf '%s\n' "$volumes" | while read -r uuid name; do
        dev=$(findfs "UUID=$uuid")
        blkid "$dev" | grep -q 'TYPE="xfs"' || exit 1
        device=$(cat "/sys/class/block/${dev##*/}/dev")
        target=/srv/evac/$name
        elsewhere=$(awk -v d="$device" -v p="$target" \
            '$3 == d && $5 != p {print FILENAME ": " $5}' \
            /proc/[0-9]*/mountinfo 2>/dev/null || true)
        [ -z "$elsewhere" ] || { echo "$dev already mounted elsewhere: $elsewhere" >&2; exit 1; }
        if mountpoint -q "$target"; then
            awk -v d="$device" -v p="$target" \
                '$3 == d && $5 == p {found=1} END {exit !found}' /proc/self/mountinfo || exit 1
        fi
        echo "$name: $dev, UUID=$uuid, target=$target"
    done
}

preflight
[ "$mode" != --check ] || exit 0
umask 077
mkdir -p /srv/evac
printf '%s\n' "$volumes" | while read -r uuid name; do
    target=/srv/evac/$name
    mkdir -p "$target"
    if ! mountpoint -q "$target"; then
        mount -t xfs -o nosuid,nodev "$(findfs "UUID=$uuid")" "$target"
    fi
    # A failed or missing mount must never redirect an evacuation onto root.
    mountpoint -q "$target"
    mkdir -p "$target/incoming-evac-20261011"
    probe=$(mktemp "$target/incoming-evac-20261011/.write-check.XXXXXX")
    printf 'evacuation write check\n' > "$probe"
    sync "$probe"
    rm "$probe"
    df -Pk "$target"
done
