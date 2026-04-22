#!/bin/sh
# `ss -s` — socket summary: total, TCP/UDP counts, orphans, timewait.
# Watch for runaway orphaned/timewait counts (ephemeral port exhaust).
exec timeout -s KILL 10s /bin/sh -c '
ss -s
' | add_prefix 'sockstat '
