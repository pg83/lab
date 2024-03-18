{% extends '//lab/services/persist/ix.sh' %}

{% set cm = cluster_map | des %}

{% block srv_command %}
set -xue

export PATH=/bin
export IX_ROOT={{wd}}/ix_root
export IX_EXEC_KIND=local
export ETCDCTL_ENDPOINTS="{{cm.etcd.ep}}"

cycle() (
    gpull https://github.com/pg83/ix ix
    cd ix
    mv \${IX_ROOT}/build/* \${IX_ROOT}/trash/ || true
    ./ix build bld/all {{ci_targets}}
)

etcdctl watch --prefix /git/logs/git_ci | gnugrep --line-buffered 'PUT' | while read l; do
    cycle || sleep 10
done
{% endblock %}
