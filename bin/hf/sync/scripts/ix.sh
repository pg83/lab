{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/hf_push_one
{% include 'hf_push_one.sh/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
