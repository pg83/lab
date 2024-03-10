{% extends '//die/proxy.sh' %}

{% block install %}
mkdir ${out}/bin ${out}/etc

cat << EOF > ${out}/bin/collectd
#!/usr/bin/env sh
set -xue
mkdir -p /home/collector
chown collector:collector /home/collector
cd /ix/realm/system/share
exec su-exec collector prometheus --config.file=/etc/prometheus.conf --storage.tsdb.path=/home/collector/
EOF

cat << EOF > ${out}/etc/prometheus.conf
{% include 'prometheus.conf' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
