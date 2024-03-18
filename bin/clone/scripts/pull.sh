#!/usr/bin/env sh

set -xue

date

(cd ${2}; git pull; git submodule update --init --recursive) || (rm -rf ${4}; git clone --recurse-submodules "${1}" ${2})
