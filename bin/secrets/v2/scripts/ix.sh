{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin
mkdir -p ${out}/share/secrets-v2

base64 -d << EOF > ${out}/bin/ix_serve_secrets_v2
{% include 'serve.py/base64' %}
EOF

base64 -d << EOF > ${out}/share/secrets-v2/store
{% include 'store/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
