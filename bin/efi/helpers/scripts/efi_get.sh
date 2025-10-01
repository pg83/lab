#!/bin/sh

set -xue

mount -o ro -t efivarfs efivarfs /sys/firmware/efi/efivars
exec cat /sys/firmware/efi/efivars/${1}-${2}
