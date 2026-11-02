#!/usr/bin/env sh

set -eu
umask 077

sha=$1
repo=quay.io/pshirshov/random
auth=quay-auth.json
trap 'rm -f "${auth}" "${sha}"' EXIT

printf '%s\n' "${QUAY_TOKEN}" | oras login \
    --registry-config "${auth}" \
    -u 'pshirshov+pg' --password-stdin quay.io

if oras manifest fetch --registry-config "${auth}" \
        --descriptor "${repo}:${sha}" >/dev/null 2>&1; then
    echo "quay: ${sha} already published"
    exit 0
fi

minio-client get "minio/cas/${sha}" "${sha}"

oras push \
    --registry-config "${auth}" \
    --concurrency 1 --no-tty \
    -a 'org.opencontainers.image.source=https://github.com/stal-ix/pkgsrc' \
    "${repo}:${sha}" "${sha}"
