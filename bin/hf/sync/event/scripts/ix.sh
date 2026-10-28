{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin
mkdir -p ${out}/etc/event/new_sha

base64 -d << EOF > ${out}/bin/hf_push_event
{% include 'hf_push_event.py/base64' %}
EOF

cat << 'EOF' > ${out}/etc/event/new_sha/hf.json
{
    "cmd": [
        "/bin/env",
        "PATH=$PATH",
        "GORN_API=$GORN_API",
        "S3_ENDPOINT=$S3_ENDPOINT",
        "MC_HOST_minio_cas=$MC_HOST_minio_cas",
        "AWS_ACCESS_KEY_ID_CAS=$AWS_ACCESS_KEY_ID_CAS",
        "AWS_SECRET_ACCESS_KEY_CAS=$AWS_SECRET_ACCESS_KEY_CAS",
        "HF_TOKEN=$HF_TOKEN",
        "hf_push_event"
    ]
}
EOF

chmod +x ${out}/bin/hf_push_event
{% endblock %}
