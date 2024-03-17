#!/usr/bin/env sh

set -xue

subreaper timeout -s TERM ${1} gwait "${2}" || sleep 5

(cd ${4}; git pull; git submodule update --init --recursive) || (rm -rf ${4}; git clone --recurse-submodules "${3}" ${4})
