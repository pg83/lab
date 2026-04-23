{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/dedup
{% include 'dedup.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
