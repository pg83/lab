#!/bin/sh
set -eu
base=/srv/evac-vpn
echo $$ > "$base/run/netns.pid"
dhcp_pid=
vpn_pid=
cleanup() {
    trap - EXIT INT TERM
    [ -z "$vpn_pid" ] || kill "$vpn_pid" 2>/dev/null || true
    [ -z "$dhcp_pid" ] || kill "$dhcp_pid" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
i=0
while ! "$base/runtime/ip" link show evac-lan >/dev/null 2>&1; do
    i=$((i+1)); [ "$i" -le 50 ] || exit 1
    sleep 0.1
done
"$base/runtime/ip" link set lo up
"$base/runtime/ip" link set evac-lan up
printf 'nameserver 10.0.0.1\n' > "$base/run/resolv.conf"
mount --bind "$base/run/resolv.conf" /etc/resolv.conf
udhcpc -f -n -R -a -i evac-lan -t 5 -T 3 -s "$base/dhcp-up.sh" > "$base/run/dhcp.log" 2>&1 &
dhcp_pid=$!
i=0
while [ ! -f "$base/run/dhcp.ready" ]; do
    kill -0 "$dhcp_pid"
    i=$((i+1)); [ "$i" -le 200 ] || { echo 'DHCP timeout' >&2; exit 1; }
    sleep 0.1
done
echo "Namespace ready: PID=$$, LAN=$(cat "$base/run/dhcp.ready")"
"$base/runtime/openvpn" --config "$base/client.ovpn" --writepid "$base/run/openvpn.pid" --log "$base/run/openvpn.log" &
vpn_pid=$!
wait "$vpn_pid"
