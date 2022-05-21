{% extends '//die/proxy.sh' %}

{% block run_deps %}
bin/runsrv
bin/sndio/sys
{% endblock %}

{% block install %}
cd ${out}; mkdir -p etc/services/sndiod; cd etc/services/sndiod

cat << EOF > run
#!/bin/sh
exec srv sndiod chrt -f 10 sndiod -d
EOF

chmod +x run
{% endblock %}
