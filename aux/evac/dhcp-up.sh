#!/bin/sh
set -eu
base=/srv/evac-vpn
[ "$interface" = evac-lan ] || exit 1
case "$1" in
bound|renew)
    /bin/ifconfig "$interface" "$ip" netmask "${subnet:-255.255.255.0}" up
    gateway=${router%% *}
    "$base/runtime/ip" route replace default via "$gateway" dev "$interface"
    : > "$base/run/lan-resolv.conf"
    for server in ${dns:-}; do
        printf 'nameserver %s\n' "$server" >> "$base/run/lan-resolv.conf"
    done
    if [ ! -s "$base/run/lan-resolv.conf" ]; then
        printf 'nameserver %s\n' "$gateway" > "$base/run/lan-resolv.conf"
    fi
    if [ ! -e "$base/run/vpn-dns.ready" ]; then
        cat "$base/run/lan-resolv.conf" > "$base/run/resolv.conf"
    fi
    printf '%s\n' "$ip" > "$base/run/dhcp.ready"
    ;;
deconfig)
    /bin/ifconfig "$interface" 0.0.0.0
    rm -f "$base/run/dhcp.ready"
    ;;
esac
