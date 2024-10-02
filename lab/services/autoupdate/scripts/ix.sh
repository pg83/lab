{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/bin

cat << EOF > ${out}/bin/ix
#!/usr/bin/env sh
exec /var/run/autoupdate_ix/ix/ix "\${@}"
EOF

cat << EOF > ${out}/bin/autoupdate_cycle
#!/usr/bin/env sh
set -xue
sleep 10
gpull https://github.com/pg83/lab ix
ix mut system
ix mut \$(ix list)
timeout 60s etcdctl watch --prefix /git/logs/git_lab | gnugrep --line-buffered 'PUT' | head -n 1
EOF

chmod +x ${out}/bin/*
{% endblock %}
