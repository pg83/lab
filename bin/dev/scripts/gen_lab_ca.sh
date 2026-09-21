#!/bin/sh

# Generate the lab's private CA once and store it in etcd_1, where the
# secrets service serves it to lab_proxy on every host:
#   /tls/lab/ca.crt   PEM certificate, also published at http://labN.mesh/ca.crt
#   /tls/lab/ca.key   PEM EC P-256 private key
# Each lab_proxy mints its own *.lab.mesh leaf from these at start.
# Skips when the key already exists; to rotate, etcdctl del both first.
#
# Run on a lab host as root with ETCDCTL_ENDPOINTS pointing at etcd_1.

set -eu

export OPENSSL_CONF=/dev/null

if [ -n "$(etcdctl get --print-value-only /tls/lab/ca.key 2>/dev/null)" ]; then
    echo "skip /tls/lab/ca.key (exists)"
    exit 0
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$TMP/ca.key"
openssl req -x509 -new -key "$TMP/ca.key" -days 7300 -subj '/CN=lab.mesh CA' \
    -addext 'basicConstraints=critical,CA:TRUE' -addext 'keyUsage=critical,keyCertSign,cRLSign' \
    -out "$TMP/ca.crt"

etcdctl put /tls/lab/ca.crt < "$TMP/ca.crt"
etcdctl put /tls/lab/ca.key < "$TMP/ca.key"

echo "wrote /tls/lab/ca.crt and /tls/lab/ca.key"
openssl x509 -in "$TMP/ca.crt" -noout -subject -enddate -fingerprint -sha256
