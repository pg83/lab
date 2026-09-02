#!/usr/bin/env sh

set -xue

sha=$1

minio-client get "minio/cas/${sha}" _

huggingface_cli upload \
    --token "${HF_TOKEN}" \
    --repo-type dataset \
    stal-ix/pkgsrc \
    _ "cas/$(echo ${sha} | cut -c1-2)/${sha}"

rm _
