#!/bin/sh
# Run in the foreground on lab1. All VPN routes stay in a new network namespace.
set -eu
base=/srv/evac-vpn
umask 077
mkdir -p "$base/run"
exec 9>"$base/run/lock"
flock -n 9 || { echo 'Evacuation VPN network is already running' >&2; exit 1; }
echo $$ > "$base/run/launcher.pid"
rm -f "$base/run/netns.pid" "$base/run/dhcp.ready" "$base/run/vpn-dns.ready"
child=
cleanup() {
    trap - EXIT INT TERM
    [ -z "$child" ] || kill "$child" 2>/dev/null || true
    [ -z "$child" ] || wait "$child" 2>/dev/null || true
    "$base/runtime/ip" link delete evac-lan 2>/dev/null || true
    rm -f "$base/run/netns.pid" "$base/run/launcher.pid"
}
trap cleanup EXIT
trap 'exit 130' INT TERM
unshare -m -n --propagation private /bin/sh "$base/netns-inner.sh" &
child=$!
i=0
while [ ! -s "$base/run/netns.pid" ]; do
    kill -0 "$child"
    i=$((i+1)); [ "$i" -le 50 ] || exit 1
    sleep 0.1
done
pid=$(cat "$base/run/netns.pid")
"$base/runtime/ip" link add link eth3 name evac-lan address 02:ec:ac:01:00:01 type macvlan mode bridge
"$base/runtime/ip" link set evac-lan netns "$pid"
wait "$child"
