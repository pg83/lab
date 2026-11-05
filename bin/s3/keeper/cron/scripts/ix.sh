{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/cron ${out}/share/s3-keeper

base64 -d << EOF > ${out}/share/s3-keeper/config.json
{{s3_config}}
EOF

cat << 'EOF' > ${out}/etc/cron/600-s3-keeper.json
{
    "cmd": ["s3", "keeper", "-c", "/ix/realm/system/share/s3-keeper/config.json"]
}
EOF
{% endblock %}
