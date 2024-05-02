{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/hooks
cat << EOF > ${out}/etc/hooks/cas.sh
#!/usr/bin/env sh
echo ""
minio-client cat "minio/cas/\${QUERY_STRING}"
EOF
chmod + ${out}/etc/hooks/*
{% endblock %}
