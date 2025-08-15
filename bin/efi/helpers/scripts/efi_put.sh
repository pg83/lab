#!/bin/sh

set -xue

mount -o rw -t efivarfs efivarfs /sys/firmware/efi/efivars
efivar efivar -n ${1} -w -f ${2}
