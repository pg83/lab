{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/ix_serve_secrets
{% include 'serve.py/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
