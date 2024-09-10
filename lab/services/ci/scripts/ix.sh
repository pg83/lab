{% extends '//die/proxy.sh' %}

{% block install %}
mkdir ${out}/bin

cat << EOF > ${out}/bin/ci_cycle
set -xue

export PATH=/bin
export IX_ROOT={{wd}}/ix_root
export IX_EXEC_KIND=local

etcdctl watch --prefix /git/logs/git_ci | gnugrep --line-buffered 'PUT' | head -n 1

gpull https://github.com/pg83/ix ix
cd ix
mv \${IX_ROOT}/build/* \${IX_ROOT}/trash/ || true
exec ./ix build bld/all {{ci_targets}}
EOF

chmod +x ${out}/bin/*
{% endblock %}
