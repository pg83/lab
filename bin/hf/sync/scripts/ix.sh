{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/hf_sync
{% include 'hf_sync.sh/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
