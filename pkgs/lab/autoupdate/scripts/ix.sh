{% extends '//die/proxy.sh' %}

{% block install %}
cd ${out}; mkdir bin; cd bin

cat << EOF > autoupdate_cycle
#!/usr/bin/env sh
set -xue
sleep 200
(cd ix; git pull) || (rm -rf ix; git clone https://github.com/pg83/ix --branch lab --single-branch ix)
cd ix
export IX_ROOT=/ix
export IX_EXEC_KIND=system
./ix mut system lab/ix.sh
./ix mut lab lab/$(hostname)
EOF

chmod +x *
{% endblock %}
