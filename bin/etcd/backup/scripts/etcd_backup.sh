#!/bin/sh
# Snapshot the primary etcd cluster, compress, upload to MinIO.
# Invoked on a gorn worker via `gorn ignite -- etcd_backup`, which
# itself is fired every 6h by job_scheduler under the
# `/lock/backup/etcd` etcdctl lock + dedup wrapper.
#
# cwd is a fresh tmpfs inside the wrap ns — scratch dies with the
# task, no cleanup needed.

set -eu

: "${AWS_ACCESS_KEY_ID:?}"
: "${AWS_SECRET_ACCESS_KEY:?}"
: "${S3_ENDPOINT:?}"
: "${ETCDCTL_ENDPOINTS:?}"

TS=$(date -u +%Y-%m-%dT%H%M%SZ)
SNAP=snap.db
BLOB=${TS}.db.zst

etcdctl snapshot save "$SNAP"
zstd -10 -q --rm "$SNAP" -o "$BLOB"

S3_SCHEME=${S3_ENDPOINT%%://*}
S3_HOST=${S3_ENDPOINT#*://}
export MC_HOST_etcd="${S3_SCHEME}://${AWS_ACCESS_KEY_ID}:${AWS_SECRET_ACCESS_KEY}@${S3_HOST}"

minio-client cp "$BLOB" "etcd/etcd/backup/${BLOB}"
echo "etcd_backup: uploaded etcd/backup/${BLOB} ($(stat -c %s "$BLOB") bytes)"
