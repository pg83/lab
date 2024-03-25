#!/bin/sh

set -xue

mkdir -p /mnt

umount ${1} || true
umount /mnt || umount -l /mnt || true

mkfs.ext4 -F ${1}

mount ${1} /mnt

python3 ./sync.py /mnt ${2}

cd /mnt

ln -s ix/realm/system/bin bin
ln -s ix/realm/system/etc etc
ln -s / usr

mkdir -p home/root var sys proc dev

mkdir -m 01777 ix/realm

cd ix/realm
ln -s ${2} system
cd /
sync
umount /mnt
