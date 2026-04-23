{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/etcd_backup
{% include 'etcd_backup.sh/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
