{% extends '//etc/services/runit/script/ix.sh' %}

{% block install %}
{{super()}}
mkdir -p ${out}/etc
cat << EOF > ${out}/etc/rsyncd.conf
[{{rsyncd_share}}]
    path = {{rsyncd_path}}
EOF
{% endblock %}

{% block srv_command %}
exec rsync \
    --daemon \
    --config=${out}/etc/rsyncd.conf \
    --verbose \
    --no-detach \
    --log-file=/dev/stdout \
    --port={{rsyncd_port}}
{% endblock %}
