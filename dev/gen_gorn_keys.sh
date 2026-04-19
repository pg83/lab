#!/bin/sh

# Generate ed25519 keypairs for every GornSsh user on every host and
# push them into etcd, where the Secrets service will pick them up.
#
# Layout in etcd (same paths the dropbear service fetches via get_key):
#   /gorn/<host>.nebula.gorn_<N>.pub
#   /gorn/<host>.nebula.gorn_<N>.priv
#
# Reads the host -> N map from GORN_N in lab/cg.py.
# Skips keys that already exist; to regenerate, etcdctl del them first.
#
# Requires: python3, ssh-keygen, etcdctl with ETCDCTL_ENDPOINTS set.

set -eu

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/parse.py" <<'PY'
import ast, sys
for node in ast.parse(open('lab/cg.py').read()).body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == 'GORN_N':
                for k, v in ast.literal_eval(node.value).items():
                    print(k, v)
                sys.exit(0)
sys.exit('GORN_N not found in lab/cg.py')
PY
pairs=$(python3 "$TMP/parse.py")

echo "$pairs" | while read -r host n; do
    i=0
    while [ "$i" -lt "$n" ]; do
        user="gorn_$i"
        base="/gorn/${host}.nebula.${user}"
        key="${TMP}/${host}.${user}"
        i=$((i + 1))

        if [ -n "$(etcdctl get --print-value-only "${base}.pub" 2>/dev/null)" ]; then
            echo "skip ${base} (exists)"
            continue
        fi

        ssh-keygen -q -t ed25519 -N '' -C "${host}.nebula:${user}" -f "$key"

        etcdctl put "${base}.pub"  < "${key}.pub"
        etcdctl put "${base}.priv" < "$key"

        echo "wrote ${base}"
    done
done
