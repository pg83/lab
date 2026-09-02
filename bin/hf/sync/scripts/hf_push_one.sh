#!/usr/bin/env sh

set -xue

sha=$1

minio-client get "minio/cas/${sha}" _

rc=0
huggingface_cli upload \
    --token "${HF_TOKEN}" \
    --repo-type dataset \
    stal-ix/pkgsrc \
    _ "cas/$(echo ${sha} | cut -c1-2)/${sha}" || rc=$?

rm -f _
sleep 30
exit "${rc}"
