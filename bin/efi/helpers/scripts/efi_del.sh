#!/bin/sh

set -xue

mount -o rw -t efivarfs efivarfs /sys/firmware/efi/efivars
chattr -i /sys/firmware/efi/efivars/${1}-${2}
exec rm /sys/firmware/efi/efivars/${1}-${2}
