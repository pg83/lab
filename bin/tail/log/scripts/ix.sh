{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/ix_tail_log
{% include 'serve.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
