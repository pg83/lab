{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/ghcr_sync
{% include 'ghcr_sync.sh/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
