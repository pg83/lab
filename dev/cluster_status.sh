#!/bin/sh

# Survey gorn / ci / molot state across the lab. Prints:
#   - per-host: runit status of gorn_*, ci, gorn_ctl; busy gorn_N endpoints
#     (active overlay mounts + wrap/molot/unshare/tar/make processes),
#     tail of service logs.
#   - cluster-wide: gorn leader, queue size, per-task descr/slots/age,
#     endpoint count.
#
# Assumes root@<host>.nebula ssh works (key-based). Queries etcd and the
# gorn control API directly from the invoking machine; one of the labs'
# control endpoints needs to be reachable.
#
# Usage: ./cluster_status.sh [host1 host2 ...]
# Default host list: lab1 lab2 lab3.

set -eu

# Stalix python3 wrapper doesn't accept `-` / `-c` for stdin/inline
# scripts — it treats argv[1] as a file path. Stage the helpers as
# real files in a temp dir.
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat > "$TMP/queue.py" <<'PY'
import json, sys
from datetime import datetime, timezone

d = json.load(sys.stdin)
tasks = d.get("tasks", [])

print(f"{len(tasks)} tasks")
now = datetime.now(timezone.utc)

def age(s):
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return "?"
    delta = now - t
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m}m"
    if m:
        return f"{m}m{sec}s"
    return f"{sec}s"

print(f"{'guid':<50} {'slots':>5}  {'age':>8}  descr")
for t in tasks:
    print(f"{t['guid']:<50} {t.get('slots',1):>5}  {age(t.get('enqueued_at','')):>8}  {t.get('descr','')}")
PY

cat > "$TMP/endpoints.py" <<'PY'
import json, sys

d = json.load(sys.stdin)
eps = d.get("endpoints", [])
by = {}

for e in eps:
    by.setdefault(e["host"], []).append(e["user"])

def idx(u):
    try:
        return int(u.rsplit("_", 1)[-1])
    except Exception:
        return -1

for h, us in sorted(by.items()):
    us.sort(key=idx)
    print(f"{h}: {len(us)} slots  ({us[0]}..{us[-1]})")
PY

HOSTS="${*:-lab1 lab2 lab3}"
# gorn_ctl (8025) binds to 127.0.0.1; gorn_ctl_nb (8027) is the nebula
# sibling exposed on the host's nebula IP.
GORN_API="${GORN_API:-http://lab1.nebula:8027}"
ETCDCTL_ENDPOINTS="${ETCDCTL_ENDPOINTS:-lab1.nebula:8020,lab2.nebula:8020,lab3.nebula:8020}"
export ETCDCTL_ENDPOINTS

hdr() {
    printf '\n==== %s ====\n' "$*"
}

#
# Cluster-wide view via etcd + gorn control.
#

hdr "gorn leader"

etcdctl get /gorn/election/ --prefix --keys-only 2>/dev/null | sort || echo "etcdctl unreachable: $ETCDCTL_ENDPOINTS"

hdr "gorn queue (${GORN_API})"

if curl -fsS "$GORN_API/v1/tasks" > "$TMP/tasks.json" 2>/dev/null; then
    python3 "$TMP/queue.py" < "$TMP/tasks.json"
else
    echo "gorn control API unreachable at $GORN_API"
fi

hdr "gorn endpoints"

if curl -fsS "$GORN_API/v1/endpoints" > "$TMP/endpoints.json" 2>/dev/null; then
    python3 "$TMP/endpoints.py" < "$TMP/endpoints.json"
else
    echo "control API unreachable"
fi

#
# Per-host deep dive.
#

for h in $HOSTS; do
    hdr "$h"
    ssh -o BatchMode=yes -o ConnectTimeout=5 "root@$h.nebula" 'sh -s' <<'REMOTE' || echo "  ssh $h failed"
set -u

# Services are under /var/run/<srv>/std/ (runsrv). "out" and "err" are
# the live stdout/stderr append streams; rotated archives live as
# sibling _*.s files.

echo '-- in-flight molot wraps (overlay mounts + temp dirs) --'
# Active task on gorn_N has an overlay mount at /ix/store rooted in
# the gorn_N's /var/run home (upper/workdir live under molot.XX).
mt=$(awk '$3=="overlay"' /proc/mounts 2>/dev/null | wc -l)
printf '  %s overlay mount(s) system-wide\n' "$mt"
for d in /var/run/gorn_[0-9]*; do
    base=$(basename "$d")
    mol=$(ls -dt "$d/std/home"/molot.* 2>/dev/null | head -1)
    [ -z "$mol" ] && continue
    # Live if a process still references the molot temp or overlay.
    pgid=$(fuser "$mol" 2>/dev/null | xargs -n1 echo 2>/dev/null | sort -u | head -3)
    age=$(stat -c %Y "$mol" 2>/dev/null)
    now=$(date +%s)
    agem=$(( (now - age) / 60 ))
    printf '  %s: %s (mtime %dm ago)%s\n' "$base" "$(basename "$mol")" "$agem" "${pgid:+, pids=$pgid}"
done

echo
echo '-- gorn_N user processes (exclude dropbear) --'
ps -eo user,pid,etime,comm,args 2>/dev/null | awk '
    /^gorn_[0-9]/ && !/dropbear/ && !/sshd:/ {print}
' | head -40 || true

echo
echo '-- gorn leader current (tail) --'
# runsrv pipes service stdout+stderr through tinylog into ./current.
tail -n 30 /var/run/gorn/std/current 2>/dev/null | tail -n 15 \
    || echo "  (no gorn leader log)"

echo
echo '-- ci current (tail) --'
tail -n 15 /var/run/ci/std/current 2>/dev/null || echo "  (no ci on this host)"
REMOTE
done
