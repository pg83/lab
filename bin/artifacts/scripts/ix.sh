{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin
base64 -d << EOF > ${out}/bin/artifacts
{% include '//lab/artifacts.py/base64' %}
EOF
chmod +x ${out}/bin/artifacts
{% endblock %}
