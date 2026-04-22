#!/bin/sh
# Routing-stack snapshot: `ip rule list` + `ip route show table all`.
# Primary consumer is the MinIO policy-routing work (see NET.md) —
# once uid-based `ip rule` is in place, this log confirms the rules
# stayed attached across reboots / fixits.
exec timeout -s KILL 10s /bin/sh -c '
ip rule list | add_prefix "iprule: "
ip route show table all | add_prefix "iproute: "
' | add_prefix 'ipdiag '
