{% extends '//die/proxy.sh' %}

{% block install %}
cd ${out}; mkdir bin; cd bin

cat << EOF > autoupdate_cycle
#!/usr/bin/env sh
set -xue
sleep 100
(cd ix; git pull; git submodule update --init --recursive) || (rm -rf ix; git clone --recurse-submodules https://github.com/pg83/lab ix)
cd ix
export IX_ROOT=/ix
export IX_EXEC_KIND=system
{% if hostname == 'host1' %}
./ix mut system --hostname=lab1
{% endif %}
{% if hostname == 'host2' %}
./ix mut system --hostname=lab2
{% endif %}
./ix mut system
./ix mut \$(./ix list)
EOF

chmod +x *
{% endblock %}
