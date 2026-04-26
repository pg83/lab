{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/nebula_ng_cert_init
{% include 'cert_init.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
