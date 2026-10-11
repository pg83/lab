{% extends '//die/gen.sh' %}

{% block run_deps %}
bin/python
bin/openssh/client
{% endblock %}

{% block install %}
mkdir -p ${out}/bin
base64 -d << EOF > ${out}/bin/evac-transfer
{% include 'transfer.py/base64' %}
EOF
base64 -d << EOF > ${out}/bin/evac-transfer-controller
{% include 'controller.py/base64' %}
EOF
base64 -d << EOF > ${out}/bin/evac-transfer-source-agent
{% include 'source_agent.py/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
