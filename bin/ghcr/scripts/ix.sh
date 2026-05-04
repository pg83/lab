{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/ghcr_push_one
{% include 'ghcr_push_one.sh/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
