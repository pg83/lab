{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin
mkdir -p ${out}/etc/event/git

base64 -d << EOF > ${out}/bin/cache_ix_event
{% include 'cache_ix_event.py/base64' %}
EOF

cat << 'EOF' > ${out}/etc/event/git/cache_ix.json
{
    "cmd": [
        "/bin/env",
        "PATH=$PATH",
        "GORN_API=$GORN_API",
        "S3_ENDPOINT=$S3_ENDPOINT",
        "MC_HOST_minio_mirror=$MC_HOST_minio_mirror",
        "MC_HOST_minio_cas=$MC_HOST_minio_cas",
        "EVENT_HTTP_PORT=$EVENT_HTTP_PORT",
        "cache_ix_event"
    ]
}
EOF

chmod +x ${out}/bin/cache_ix_event
{% endblock %}
