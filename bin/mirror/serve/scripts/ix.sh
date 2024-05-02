{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/hooks
cat << EOF > ${out}/etc/hooks/cas.sh
#!/usr/bin/env sh
echo "Content-Type: application/stream"
echo ""
export HOME=${TMPDIR}/mctmp
mkdir -p ${HOME}
# TODO(pg): validate input
minio-client cat "minio/cas/\${QUERY_STRING}"
EOF
chmod +x ${out}/etc/hooks/*
{% endblock %}
