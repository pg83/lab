{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin
mkdir -p ${out}/etc/event/new_sha

base64 -d << EOF > ${out}/bin/modelscope_push_event
{% include 'modelscope_push_event.py/base64' %}
EOF

cat << 'EOF' > ${out}/etc/event/new_sha/modelscope.json
{
    "cmd": [
        "/bin/env",
        "PATH=$PATH",
        "GORN_API=$GORN_API",
        "MC_HOST_minio_cas=$MC_HOST_minio_cas",
        "MODELSCOPE_TOKEN=$MODELSCOPE_TOKEN",
        "modelscope_push_event"
    ]
}
EOF

chmod +x ${out}/bin/modelscope_push_event
{% endblock %}
