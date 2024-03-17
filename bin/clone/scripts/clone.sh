#!/usr/bin/env sh

set -xue

(subreaper timeout -s KILL ${1} sh ./wait.sh "${2}") || sleep 30

(cd ${4}; git pull; git submodule update --init --recursive) || (rm -rf ${4}; git clone --recurse-submodules "${3}" ${4})
