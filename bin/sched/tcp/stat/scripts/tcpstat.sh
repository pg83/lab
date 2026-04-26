#!/bin/sh
# TCP-level counters from /proc/net/snmp (Tcp: line) and
# /proc/net/netstat (TcpExt: line). The latter is where the
# retransmit-flavour fields live: RetransSegs, TCPLossProbes,
# TCPSlowStartRetrans, TCPDSACKRecv (= peer told us a segment
# was a duplicate, i.e. our retransmit was spurious),
# TCPDSACKOfoRecv (out-of-order DSACK), TCPLostRetransmit, etc.
#
# A retransmit storm with high TCPDSACKRecv = our reorder buffer
# isn't catching everything and TCP is fast-retransmitting on
# innocent reorder. High TCPLostRetransmit / Timeouts = real loss.
exec timeout -s KILL 10s awk '
    /^Tcp:/ {
        if (tcp_header == "") {
            for (i = 2; i <= NF; i++) tcp_keys[i] = $i
            tcp_header = 1

            next
        }

        line = ""

        for (i = 2; i <= NF; i++) {
            line = line tcp_keys[i] "=" $i " "
        }

        print "tcp " line
    }
    /^TcpExt:/ {
        if (ext_header == "") {
            for (i = 2; i <= NF; i++) ext_keys[i] = $i
            ext_header = 1

            next
        }

        line = ""

        for (i = 2; i <= NF; i++) {
            line = line ext_keys[i] "=" $i " "
        }

        print "tcpext " line
    }
' /proc/net/snmp /proc/net/netstat | add_prefix 'tcpstat '
