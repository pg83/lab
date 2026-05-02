#!/bin/sh

# One-shot cleanup for the gorn → molot bucket split. Run after deploying
# the ci.py S3_BUCKET=molot change. Drops the two caches that would
# otherwise prevent self-healing: cix/complete (molot's "uid completed,
# skip dispatch" set) and gorn/gorn/* (gorn wrap's HEAD <uid>/result.json
# idempotency cache + recent task logs). Without this the new molot still
# hits already-done short-circuits and never uploads artifacts to the
# new s3://molot/molot/<uid>/ location, so downstream nodes 404 forever.

set -eux

: "${AWS_ACCESS_KEY_ID:?}"
: "${AWS_SECRET_ACCESS_KEY:?}"
: "${S3_ENDPOINT:?}"

S3_SCHEME="${S3_ENDPOINT%%://*}"
S3_HOST="${S3_ENDPOINT#*://}"
export MC_HOST_minio="${S3_SCHEME}://${AWS_ACCESS_KEY_ID}:${AWS_SECRET_ACCESS_KEY}@${S3_HOST}"

minio-client du minio/cix/ minio/gorn/gorn/ minio/gorn/molot/

minio-client rm minio/cix/complete
minio-client rm --recursive --force minio/gorn/gorn/
minio-client rm --recursive --force minio/gorn/molot/

minio-client du minio/cix/ minio/gorn/gorn/ minio/gorn/molot/

echo "drop_molot_legacy_caches: done"
