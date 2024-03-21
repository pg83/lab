{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/hooks

cat << EOF > ${out}/etc/hooks/favicon.ico
#!/usr/bin/env sh
echo "Content-Type: text/plain"
echo ""
echo "Dupa"
EOF

cat << EOF > ${out}/etc/hooks/{{evlog_topic}}.sh
#!/usr/bin/env sh
echo "Content-Type: text/plain"
echo ""
(date; cat) | etcdctl put /git/logs/{{evlog_topic}}
EOF

chmod +x ${out}/etc/hooks/*
{% endblock %}
