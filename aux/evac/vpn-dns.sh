#!/bin/sh
set -eu
base=/srv/evac-vpn
case "$script_type" in
up)
    env | awk '/^foreign_option_[0-9]+=dhcp-option DNS[6]? [0-9a-fA-F:.]+$/ {print "nameserver " $NF}' > "$base/run/vpn-resolv.conf"
    if [ -s "$base/run/vpn-resolv.conf" ]; then
        cat "$base/run/vpn-resolv.conf" > "$base/run/resolv.conf"
        touch "$base/run/vpn-dns.ready"
    fi
    ;;
down)
    cat "$base/run/lan-resolv.conf" > "$base/run/resolv.conf"
    rm -f "$base/run/vpn-dns.ready"
    ;;
esac
