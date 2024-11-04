{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/$(dirname {{file_path}})
base64 -d << EOF > ${out}/{{file_path}}
{{file_data}}
EOF
chmod +x ${out}/bin/* || true
{% endblock %}
