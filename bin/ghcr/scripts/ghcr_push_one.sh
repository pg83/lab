#!/usr/bin/env sh

set -xue

sha=$1

mkdir tmp
cd tmp

minio-client get "minio/cas/${sha}" "${sha}"

oras push \
    -u pg83 \
    -p "${GHCR_TOKEN}" \
    -a "org.opencontainers.image.source=https://github.com/stal-ix/pkgsrc" \
    "ghcr.io/stal-ix/pkgsrc/$(echo ${sha} | cut -c1-1):${sha}" \
    "${sha}"

cd ..
rm -rf tmp
