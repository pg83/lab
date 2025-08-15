#!/bin/sh

set -xue

mount -o ro -t efivarfs efivarfs /sys/firmware/efi/efivars
efivar -n ${1} -e /dev/stdout
