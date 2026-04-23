{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/etcd_defrag
{% include 'etcd_defrag.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
