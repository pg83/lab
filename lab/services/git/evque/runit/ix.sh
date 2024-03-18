{% extends '//etc/services/runit/script/ix.sh' %}

{% set cm = cluster_map | des %}

{% block srv_command %}
set -xue

export ETCDCTL_ENDPOINTS=localhost:{{cm.etcd.ports.client}}

gosmee client --saveDir \${PWD} --noReplay "{{evlog_url}}" qw 2>&1 | gnugrep --line-buffered 'has been saved' | while read l; do
    cat *.json | etcdctl put /git/logs/{{evlog_user}}
    rm -f *
done
{% endblock %}
