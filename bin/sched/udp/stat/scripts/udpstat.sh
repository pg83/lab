#!/bin/sh
# UDP-level counters from /proc/net/snmp. The values most worth
# watching for the link_join setup are RcvbufErrors and MemErrors
# — they grow when softirq RX outpaces application drain (which is
# what happens when gofra's 4-NIC stripe bursts into a too-small
# SO_RCVBUF or netdev_max_backlog).
#
# Format: header line gives field names, value line gives ints.
# Skip UdpLite (we don't use it) and the header lines themselves.
exec timeout -s KILL 10s awk '
    /^Udp:/ {
        if (header == "") {
            for (i = 2; i <= NF; i++) keys[i] = $i
            header = 1
            next
        }

        line = ""

        for (i = 2; i <= NF; i++) {
            line = line keys[i] "=" $i " "
        }

        print line
    }
' /proc/net/snmp | add_prefix 'udpstat '
