#!/bin/sh

# Test harness for NET.md Option A (UID-based policy routing to pin
# each minio_N daemon's egress to its own ethN). Applies/verifies/rolls
# back without touching MINIO_SCRIPT or cg.py. Once we're sure it
# behaves, we fold the same three commands into MINIO_SCRIPT.
#
# Usage:
#   ./pin_minio_nic.sh apply     [host...]    # default lab1 lab2 lab3
#   ./pin_minio_nic.sh rollback  [host...]
#   ./pin_minio_nic.sh status    [host...]
#
# apply and rollback are idempotent: re-running apply is a no-op;
# rollback silently ignores a missing rule or empty table.
#
# Per-host mapping (from cg.py gen_host/gen_net, ip base = 64+(n-1)*4):
#   lab1  eth1=10.0.0.65  eth2=10.0.0.66  eth3=10.0.0.67
#   lab2  eth1=10.0.0.69  eth2=10.0.0.70  eth3=10.0.0.71
#   lab3  eth1=10.0.0.73  eth2=10.0.0.74  eth3=10.0.0.75
#
# uid → NIC:
#   1013 → eth1 (minio_1)
#   1014 → eth2 (minio_2)
#   1015 → eth3 (minio_3)
#
# Kernel table id = uid. ip rule priority = 1000 (between local=0 and
# main=32766). No default route in our per-uid table — off-subnet
# lookups fall through to the main table and egress via eth0 as usual.

set -eu

MODE="${1:-}"

case "$MODE" in
    apply|rollback|status) ;;
    *) echo "usage: $0 apply|rollback|status [host...]" >&2; exit 2 ;;
esac

shift

if [ "$#" -gt 0 ]; then
    HOSTS="$*"
else
    HOSTS="lab1 lab2 lab3"
fi

host_ip_base() {
    # n in cg.py's gen_host; base octet is 64 + (n-1)*4.
    case "$1" in
        lab1) echo 64 ;;
        lab2) echo 68 ;;
        lab3) echo 72 ;;
        *) echo "unknown host: $1" >&2; return 3 ;;
    esac
}

for h in $HOSTS; do
    BASE=$(host_ip_base "$h")

    ssh -o ConnectTimeout=5 "root@${h}.nebula" \
        "MODE='$MODE' BASE='$BASE' HN='$h' sh -s" <<'REMOTE'
set -u

printf '\n====================  %s  (%s)  ====================\n' "$HN" "$MODE"

# (uid, nic, octet_offset) per minio instance.
for line in "1013 eth1 1" "1014 eth2 2" "1015 eth3 3"; do
    set -- $line
    U=$1
    NIC=$2
    OFF=$3
    IP="10.0.0.$((BASE + OFF))"
    TBL=$U
    # Probe: pick a non-self peer on the matching NIC subnet. For
    # uid=1013 (eth1), probe ethN=OFF of "some other host". Lab1/3
    # probe lab2; lab2 probes lab1. This way the answer isn't "lo"
    # and reflects the actual cross-host decision.
    if [ "$HN" = "lab2" ]; then
        PROBE_BASE=64
    else
        PROBE_BASE=68
    fi
    PROBE="10.0.0.$((PROBE_BASE + OFF))"

    case "$MODE" in
        apply)
            ip route replace 10.0.0.0/24 dev "$NIC" src "$IP" table "$TBL"
            # Don't silence errors blindly — "File exists" on re-apply
            # is fine, anything else means syntax/kernel mismatch.
            ERR=$(ip rule add uidrange "$U-$U" lookup "$TBL" priority 1000 2>&1 1>/dev/null) || true
            case "$ERR" in
                '') ;;
                *'File exists'*) ;;
                *) echo "  ip rule add FAILED: $ERR" ;;
            esac
            echo "applied: uid=$U nic=$NIC src=$IP table=$TBL"
            ;;
        rollback)
            ip rule del uidrange "$U-$U" lookup "$TBL" priority 1000 2>/dev/null || true
            ip route flush table "$TBL" 2>/dev/null || true
            echo "rolled back: uid=$U table=$TBL"
            ;;
        status)
            echo "-- uid=$U (expected: nic=$NIC src=$IP) --"
            echo "  rule:   $(ip rule show | grep "uidrange $U-$U" || echo '(none)')"
            echo "  table:  $(ip route show table "$TBL" 2>/dev/null | tr '\n' ';' | sed 's/;$//' || echo '(none)')"
            # Impersonate the uid so the kernel runs the full rule chain.
            # Stalix iproute2 doesn't accept `ip route get ... uid N`;
            # su-exec works by giving the child real effective uid.
            echo "  route get $PROBE as uid=$U:"
            su-exec "$U" ip route get "$PROBE" 2>&1 | sed 's/^/    /'
            ;;
    esac
done
REMOTE
done
