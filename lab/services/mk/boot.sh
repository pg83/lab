#!/bin/sh

set -xue

mkdir -p /mnt

umount ${2} || true
umount /mnt || umount -l /mnt || true
mkfs.fat -F32 ${2}
mount ${2} /mnt

grub-install --verbose --target=x86_64-efi \
    --boot-directory=/mnt/boot \
    --efi-directory=/mnt \
    --removable \
    ${1}

sync

umount /mnt
