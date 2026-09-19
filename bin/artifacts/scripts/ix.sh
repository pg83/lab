{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin
base64 -d << EOF > ${out}/bin/artifacts
{% include 'artifacts.py/base64' %}
EOF
chmod +x ${out}/bin/artifacts
{% endblock %}
