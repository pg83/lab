{% extends '//bin/minio/daemon/ix.sh' %}

{% block patch %}
{{super()}}
sed -e 's|func mustGetLocalIPs|func mustGetLocalIPsXXX|' \
    -e 's|"errors"|"errors"; "os"|' \
    -i cmd/net.go
cat << EOF >> cmd/net.go
func mustGetLocalIPs() (ipList []net.IP) {
    res := os.Getenv("MINIO_LOCAL_IP")
    if len(res) > 0 {
        return []net.IP{net.ParseIP(res)}
    }
    return mustGetLocalIPsXXX()
}
EOF
{% endblock %}
