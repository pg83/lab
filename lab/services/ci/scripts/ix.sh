{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

cat << EOF > ${out}/bin/ci_cycle
#!/usr/bin/env sh

set -xue

export PATH=/bin:/ix/realm/boot/bin
export IX_ROOT={{wd}}/ix_root
export IX_EXEC_KIND=local

sleep 10

gpull https://github.com/pg83/ix ix

cd ix

./ix build bld/all
./ix build {{ci_targets}} --jail=1 --seed=1 --tmpfs=1

timeout 60s etcdctl watch --prefix /git/logs/git_ci | gnugrep --line-buffered 'PUT' | head -n 1
EOF

chmod +x ${out}/bin/*
{% endblock %}
