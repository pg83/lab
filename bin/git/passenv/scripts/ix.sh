{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin
base64 -d << EOF > ${out}/bin/passenv
{% include 'passenv.py/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
