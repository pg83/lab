#!/usr/bin/env sh

set -xue

SYNC_DIR=$(dirname $(echo ${PATH} | tr ':' '\n' | grep '-rlm-'))

lab_boot ${1}
lab_sync ${2} ${SYNC_DIR}
