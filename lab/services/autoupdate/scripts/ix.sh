{% extends '//die/proxy.sh' %}

{% block install %}
cd ${out}; mkdir bin; cd bin

cat << EOF > ix
#!/usr/bin/env sh
exec /var/run/autoupdate_ix/ix "\${@}"
EOF

cat << EOF > autoupdate_cycle
#!/usr/bin/env sh
set -xue
sleep 100
(cd ix; git pull; git submodule update --init --recursive) || (rm -rf ix; git clone --recurse-submodules https://github.com/pg83/lab ix)
cd ix
export IX_ROOT=/ix
export IX_EXEC_KIND=system
./ix mut system
./ix mut \$(./ix list)
EOF

chmod +x *
{% endblock %}
