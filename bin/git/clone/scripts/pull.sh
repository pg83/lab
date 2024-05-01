#!/usr/bin/env sh

set -xue

(cd ${2}; git pull; git submodule update --init --recursive) || (rm -rf ${2}; git clone --recurse-submodules "${1}" ${2})
