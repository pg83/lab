#!/usr/bin/env sh

set -xue

tail -F -n 0 "${1}" | grep 'has been saved' | while read l; do
    kill -TERM -$PPID -$$
done
