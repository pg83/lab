#!/usr/bin/env sh

set -xue

waitev() (
    subreaper timeout "${1}" gosmee client --noReplay "${2}" qw 2>&1 | while read l; do
        #exit 0
        echo ${l}
    done
)

waitev "${1}" "${2}"
