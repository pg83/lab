{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/etcd_wrap
{% include 'etcd_wrap.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
