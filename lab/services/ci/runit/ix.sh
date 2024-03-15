{% extends '//lab/services/persist/ix.sh' %}

{% block srv_command %}
set -xue

export PATH=/bin:/ix/realm/boot/bin

env

sleep 200

(cd ix; git pull) || (rm -rf ix; git clone https://github.com/pg83/ix)
cd ix

export IX_ROOT={{wd}}/ix_root
export IX_EXEC_KIND=local

mv \${IX_ROOT}/build/* \${IX_ROOT}/trash/ || true

./ix build bld/all {{ci_targets}}
{% endblock %}