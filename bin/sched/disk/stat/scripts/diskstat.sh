#!/bin/sh
# Snapshot of /proc/diskstats (since-boot cumulative). Useful mostly
# via rate(...) downstream, or via diff against the previous tick in
# ad-hoc log queries. Columns:
#   major minor name reads_completed reads_merged sectors_read time_reading
#   writes_completed writes_merged sectors_written time_writing
#   in_flight time_in_queue time_weighted
# One line per real block device; filter out the virtual ones.
exec timeout -s KILL 5s /bin/sh -c '
awk "\$3 ~ /^(sd[a-z]+|nvme[0-9]+n[0-9]+)$/ {print}" /proc/diskstats
' | add_prefix 'diskstat '
