{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin
mkdir -p ${out}/etc/event/git

base64 -d << EOF > ${out}/bin/ci_hook
{% include 'ci_hook.py/base64' %}
EOF

cat << 'EOF' > ${out}/etc/event/git/ci.json
{
    "cmd": [
        "/bin/env",
        "PATH=$PATH",
        "GORN_API=$GORN_API",
        "S3_ENDPOINT=$S3_ENDPOINT",
        "AWS_ACCESS_KEY_ID_CIX=$AWS_ACCESS_KEY_ID_CIX",
        "AWS_SECRET_ACCESS_KEY_CIX=$AWS_SECRET_ACCESS_KEY_CIX",
        "ETCD_TMPFS_ENDPOINTS=$ETCD_TMPFS_ENDPOINTS",
        "ci_hook"
    ]
}
EOF

chmod +x ${out}/bin/ci_hook
{% endblock %}
