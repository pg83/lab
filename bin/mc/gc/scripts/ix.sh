{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/mc_gc
{% include 'mc_gc.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
