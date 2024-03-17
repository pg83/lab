#!/usr/bin/env sh

set -xue

(gosmee client --saveDir ${PWD} --noReplay "${1}" qw 2>&1) | grep 'has been saved' | while read l; do
    killall -9 gosmee
    exit 0
done
