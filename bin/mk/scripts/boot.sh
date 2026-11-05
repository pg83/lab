#!/usr/bin/env sh

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

# the root is the second partition of the disk this GRUB was loaded
# from: other disks are never probed, an xfs on one of them sent GRUB
# into a boot loop
cat << 'EOF' > /mnt/boot/grub/grub.cfg
insmod regexp
regexp --set=1:disk '^([^,]+),' "$root"
set root=$disk,gpt2
configfile /etc/grub.cfg
EOF

sync

umount /mnt
