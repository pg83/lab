{% extends '//lab/services/persist/ix.sh' %}

{% block srv_command %}
set -xue

export PATH=/bin:/ix/realm/boot/bin
export IX_ROOT={{wd}}/ix_root
export IX_EXEC_KIND=local

cycle() (
    gpull https://github.com/pg83/ix ix
    cd ix
    mv \${IX_ROOT}/build/* \${IX_ROOT}/trash/ || true
    ./ix build bld/all {{ci_targets}}
)

tail -F -n 0 /var/run/evlog_git_ci/events | grep 'has been saved' | while read l; do
    cycle || sleep 10
done
{% endblock %}
