{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/modelscope_push_one
{% include 'modelscope_push_one.py/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
