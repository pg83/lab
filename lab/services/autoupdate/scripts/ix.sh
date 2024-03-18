{% extends '//die/proxy.sh' %}

{% set cm = cluster_map | des %}

{% block install %}
cd ${out}; mkdir bin; cd bin

cat << EOF > ix
#!/usr/bin/env sh
exec /var/run/autoupdate_ix/ix/ix "\${@}"
EOF

cat << EOF > autoupdate_cycle
#!/usr/bin/env sh
set -xue

export PATH=/bin
export IX_ROOT=/ix
export IX_EXEC_KIND=system
export ETCDCTL_ENDPOINTS="{{cm.etcd.ep}}"

cycle() (
    gpull https://github.com/pg83/lab ix
    cd ix
    ./ix mut system
    ./ix mut \$(./ix list)
)

etcdctl watch --prefix /git/logs/ | gnugrep --line-buffered 'PUT' | while read l; do
    cycle || sleep 10
done
EOF

chmod +x *
{% endblock %}
