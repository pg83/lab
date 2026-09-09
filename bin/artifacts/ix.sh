{% extends '//die/gen.sh' %}

{% block run_deps %}
bin/python
bin/minio/patched/client
{% endblock %}

{% block install %}
mkdir -p ${out}/bin
base64 -d << EOF > ${out}/bin/artifacts
{% include '//lab/artifacts.py/base64' %}
EOF
chmod +x ${out}/bin/artifacts
{% endblock %}
