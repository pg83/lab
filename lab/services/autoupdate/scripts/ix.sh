{% extends '//die/proxy.sh' %}

{% block install %}
cd ${out}; mkdir bin; cd bin

cat << EOF > ix
#!/usr/bin/env sh
exec /var/run/autoupdate_ix/ix/ix "\${@}"
EOF

cat << EOF > autoupdate_cycle
#!/usr/bin/env bash
set -xue

export PATH=/bin
export IX_ROOT=/ix
export IX_EXEC_KIND=system

cycle() (
    gpull https://github.com/pg83/lab ix
    cd ix
    ./ix mut system
    ./ix mut \$(./ix list)
)

tail -F -n 0 /var/run/evlog_git_lab/events /var/run/hz/hz | grep 'has been saved' | while read l; do
    date
    (cycle || sleep 10) || true
done
EOF

chmod +x *
{% endblock %}
