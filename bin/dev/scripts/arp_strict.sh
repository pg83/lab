#!/bin/sh

# Host-wide ARP tightening for multi-NIC same-subnet deployments.
# Default Linux has arp_ignore=0 / arp_announce=0: any NIC answers any
# ARP query for any local IP, and outgoing ARPs pick an arbitrary NIC
# MAC as source. With N NICs on the same L2, peers' ARP caches end up
# non-deterministic — `10.0.0.65 → <any of N MACs>` — and the L2 switch
# forwards traffic for `.65` onto whichever port happens to be cached.
# Physical-cable parallelism collapses.
#
# arp_ignore=1  → reply only on the NIC that actually has the target IP
# arp_announce=2 → use the MAC of the NIC whose IP is in the src field
#
# Combined: peers learn deterministic (IP, MAC) pairs that match
# physical cables, and the L2 switch's MAC table lines up. When paired
# with per-uid policy routing (pin_minio_nic.sh, NET.md Option A), all
# layers agree which cable each logical flow uses — actual
# multi-Gbps aggregate becomes reachable.
#
# Rollback sets values back to 0 (kernel defaults). Flushes the
# neighbor table in both directions so peers re-resolve cleanly.
#
# Usage:
#   ./arp_strict.sh apply     [host...]    # default lab1 lab2 lab3
#   ./arp_strict.sh rollback  [host...]
#   ./arp_strict.sh status    [host...]

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

for h in $HOSTS; do
    ssh -o ConnectTimeout=5 "root@${h}.nebula" \
        "MODE='$MODE' HN='$h' sh -s" <<'REMOTE'
set -u

export PATH=/ix/realm/ip/bin:$PATH

printf '\n====================  %s  (%s)  ====================\n' "$HN" "$MODE"

set_knob() {
    # sysctl -w, silencing the success echo; failure still shows.
    sysctl -w "$1=$2" >/dev/null
}

apply_set() {
    # Effective value on a NIC = max(all, default, <nic>). Setting .all
    # is sufficient to force every existing and future NIC. .default
    # is inherited by NICs that come up later.
    set_knob net.ipv4.conf.all.arp_ignore      "$1"
    set_knob net.ipv4.conf.all.arp_announce    "$2"
    set_knob net.ipv4.conf.default.arp_ignore  "$1"
    set_knob net.ipv4.conf.default.arp_announce "$2"
}

case "$MODE" in
    apply)
        apply_set 1 2
        ip -s -s neigh flush all >/dev/null
        echo "applied: arp_ignore=1 arp_announce=2 (neigh table flushed)"
        ;;
    rollback)
        apply_set 0 0
        ip -s -s neigh flush all >/dev/null
        echo "rolled back: arp_ignore=0 arp_announce=0 (neigh table flushed)"
        ;;
    status)
        echo "-- sysctl --"
        for k in net.ipv4.conf.all.arp_ignore      net.ipv4.conf.all.arp_announce \
                 net.ipv4.conf.default.arp_ignore  net.ipv4.conf.default.arp_announce \
                 net.ipv4.conf.eth0.arp_ignore     net.ipv4.conf.eth0.arp_announce \
                 net.ipv4.conf.eth1.arp_ignore     net.ipv4.conf.eth1.arp_announce \
                 net.ipv4.conf.eth2.arp_ignore     net.ipv4.conf.eth2.arp_announce \
                 net.ipv4.conf.eth3.arp_ignore     net.ipv4.conf.eth3.arp_announce; do
            v=$(sysctl -n "$k" 2>/dev/null || echo '?')
            printf '  %-44s %s\n' "$k" "$v"
        done

        echo
        echo "-- local (NIC, IP, MAC) --"
        for n in eth0 eth1 eth2 eth3; do
            [ -d "/sys/class/net/$n" ] || continue
            mac=$(cat "/sys/class/net/$n/address" 2>/dev/null || echo '?')
            ip4=$(ip -4 -br addr show dev "$n" 2>/dev/null \
                  | awk '{print $3}' | head -1)
            printf '  %-6s  %-20s  %s\n' "$n" "${ip4:-(none)}" "$mac"
        done

        echo
        echo "-- neigh table (top 10 by IP) --"
        ip -4 neigh | awk '$1 != "" {print $1, $(NF-1), $NF}' | sort -V | head -10
        ;;
esac
REMOTE
done
