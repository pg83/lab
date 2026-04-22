#!/bin/sh
# loadavg / uptime / FD usage in one line each. Catches fd leaks and
# persistent load spikes.
exec timeout -s KILL 5s /bin/sh -c '
echo "loadavg $(cat /proc/loadavg)"
echo "uptime $(cat /proc/uptime)"
echo "file-nr $(cat /proc/sys/fs/file-nr)"
' | add_prefix 'load '
