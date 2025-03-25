#!/usr/bin/env sh

set -xue

mkdir -p /mnt

umount ${1} || true
umount /mnt || umount -l /mnt || true

mkfs.xfs -f ${1}

mount ${1} /mnt

lab_sync_py /mnt ${2}

cd /mnt

ln -s ix/realm/system/bin bin
ln -s ix/realm/system/etc etc
ln -s / usr

mkdir -p home/root var sys proc dev

mkdir -m 01777 ix/realm
mkdir -m 01777 ix/trash

cd ix/realm

ln -s ${2} system
ln -s ${2} boot
chown -h ix:ix system boot

cd /

sync
umount /mnt
