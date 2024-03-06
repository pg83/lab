{% extends '//die/proxy.sh' %}

{% block install %}
mkdir ${out}/bin ${out}/etc

cat << EOF > ${out}/bin/collectd
#!/usr/bin/env sh
set -xue
cd /ix/realm/system/share
exec prometheus --config.file=/etc/prometheus.conf --storage.tsdb.path=/var/run/collector/
EOF

cat << EOF > ${out}/etc/prometheus.conf
{% include 'prometheus.conf' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
