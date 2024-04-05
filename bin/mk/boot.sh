#!/bin/sh

set -xue

mkdir -p /mnt

umount ${1} || true
umount /mnt || umount -l /mnt || true
mkfs.fat -F32 ${1}
mount ${1} /mnt

grub-install --verbose --target=x86_64-efi \
    --boot-directory=/mnt/boot \
    --efi-directory=/mnt \
    --removable \
    ${1}

cat << EOF > /mnt/boot/grub/grub.cfg
set root=hd0,2
configfile /etc/grub.cfg
set root=hd1,2
configfile /etc/grub.cfg
set root=hd2,2
configfile /etc/grub.cfg
set root=hd3,2
configfile /etc/grub.cfg
set root=hd4,2
configfile /etc/grub.cfg
sync

umount /mnt
