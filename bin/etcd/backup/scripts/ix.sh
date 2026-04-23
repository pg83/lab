{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/etcd_backup
{% include 'etcd_backup.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
