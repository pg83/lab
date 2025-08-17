#!/bin/sh

set -xue

mount -o rw -t efivarfs efivarfs /sys/firmware/efi/efivars
exec efivar -n ${2}-${1} -w -f ${3}
