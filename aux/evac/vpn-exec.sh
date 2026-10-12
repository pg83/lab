#!/bin/sh
# Execute a downloader in the evacuation VPN's network and mount namespaces.
set -eu
base=/srv/evac-vpn
pid=$(cat "$base/run/netns.pid")
case "$pid" in ''|*[!0-9]*) exit 1 ;; esac
tr '\000' '\n' < "/proc/$pid/cmdline" | grep -qx "$base/netns-inner.sh" || {
    echo 'VPN namespace process is not running' >&2; exit 1;
}
[ "$(readlink /proc/self/ns/net)" != "$(readlink "/proc/$pid/ns/net")" ] || {
    echo 'Expected a separate VPN namespace' >&2; exit 1;
}
exec nsenter -t "$pid" -n -m -- "$@"
