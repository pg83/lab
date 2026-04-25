{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/ogorod_mirror
{% include 'ogorod_mirror.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
