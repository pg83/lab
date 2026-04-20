#!/bin/sh

# Trace a single molot-dispatched gorn task: what the S3 prefix
# actually has, gorn's idea of the task's state, and (if a run ever
# completed) the uploaded stdout/stderr + result.json.
#
# Use when molot reports "Unable to prepare URL for copying" on a
# dep's result.zstd — pass the dep's guid and see whether the
# producer uploaded anything at all, whether gorn thinks the task is
# queued/done/nonexistent, and if done, the exit code + logs.
#
# Requires (set via /etc/profile.d on lab hosts):
#   GORN_API         — http://127.0.0.1:8025
#   MC_HOST_minio    — http://user:pass@<host>.eth1:8012
#
# Usage:
#   ./molot_trace.sh <guid> [root]
# root defaults to "molot" (the prefix molot uses for its S3 keys);
# pass "cli" / "gorn" / etc. for non-molot tasks.

set -eu

guid="${1:?usage: molot_trace.sh <guid> [root]}"
root="${2:-molot}"

: "${GORN_API:?GORN_API not set (check /etc/profile.d/100-etcd)}"
: "${MC_HOST_minio:?MC_HOST_minio not set (check /etc/profile.d/100-etcd)}"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/parse_state.py" <<'PY'
import json, sys
d = json.load(sys.stdin)
print(d.get("state", "?"))
PY

cat > "$TMP/parse_output.py" <<'PY'
import json, sys, base64

d = json.load(sys.stdin)

res = d.get("result")

if isinstance(res, str):
    try:
        res = json.loads(res)
    except Exception:
        pass

print("---- result.json ----")
print(json.dumps(res, indent=2, sort_keys=True))
print()

for stream in ("stdout", "stderr"):
    print(f"---- {stream} ----")
    raw = d.get(f"{stream}_b64", "")
    if raw:
        print(base64.b64decode(raw).decode(errors="replace"))
    else:
        print(f"(empty {stream})")
    print()
PY

echo "guid: $guid"
echo "root: $root"
echo

echo "==== S3: minio/gorn/$root/$guid/ ===="
minio-client ls "minio/gorn/$root/$guid/" 2>&1 || echo "(mc ls failed — bucket/prefix empty or unreachable)"
echo

echo "==== gorn state: GET $GORN_API/v1/tasks/$guid?root=$root ===="
state_json=$(curl -sS "$GORN_API/v1/tasks/$guid?root=$root")
echo "$state_json"
state=$(echo "$state_json" | python3 "$TMP/parse_state.py")
echo
echo "parsed state: $state"
echo

if [ "$state" = "done" ]; then
    echo "==== gorn output: GET $GORN_API/v1/tasks/$guid/output?root=$root ===="
    curl -sS "$GORN_API/v1/tasks/$guid/output?root=$root" | python3 "$TMP/parse_output.py"
elif [ "$state" = "queued" ]; then
    echo "task is still queued — never picked up, or picked up and failed retriably"
elif [ "$state" = "not_found" ]; then
    echo "task is nowhere: not in queue and no result.json at gorn/$root/$guid/"
    echo "suggests the producer never finished and gorn has no record — check S3 listing above for stray stdout/stderr"
fi
