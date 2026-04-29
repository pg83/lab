{% extends '//bin/minio/daemon/ix.sh' %}

{% block patch %}
{{super()}}
sed -e 's|func mustGetLocalIPs|func mustGetLocalIPsXXX|' \
    -e 's|"errors"|"errors"; "os"|' \
    -i cmd/net.go
cat << EOF >> cmd/net.go
func mustGetLocalIPs() (ipList []net.IP) {
    res := os.Getenv("LAB_LOCAL_IP")
    if len(res) > 0 {
        // Return LAB_LOCAL_IP plus loopback so getServerListenAddrs()
        // adds 127.0.0.1 to the bind set — local clients (mc, ogorod_serve,
        // gorn workers) reach minio over loopback without going through the
        // overlay.
        return []net.IP{net.ParseIP(res), net.ParseIP("127.0.0.1")}
    }
    return mustGetLocalIPsXXX()
}
EOF
{% endblock %}
