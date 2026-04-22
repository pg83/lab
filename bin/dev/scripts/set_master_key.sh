#!/bin/sh

# Push the secrets_v2 master passphrase into pers_db on every lab
# host. The passphrase is used by the secrets_v2 service to decrypt
# the git-committed store blob on startup. persdb_put reads its value
# from a file whose path equals the key name — so we stage argv[1]
# into /master.key, put it, then wipe.
#
# Usage:
#   ./set_master_key.sh <passphrase>            # default hosts lab{1,2,3}
#   ./set_master_key.sh <passphrase> lab1 lab2  # explicit subset
#
# Assumes key-based ssh as root@<host>.nebula works.

set -eu

if [ "$#" -lt 1 ]; then
    echo "usage: $0 <passphrase> [host...]" >&2
    exit 2
fi

PP="$1"
shift

if [ "$#" -gt 0 ]; then
    HOSTS="$*"
else
    HOSTS="lab1 lab2 lab3"
fi

for h in $HOSTS; do
    echo "=== $h ==="
    ssh "root@${h}.nebula" "
        set -eu
        umask 077
        printf '%s' '$PP' > /master.key
        persdb_put /master.key
        shred -u /master.key 2>/dev/null || rm -f /master.key
        echo 'ok'
    "
done
