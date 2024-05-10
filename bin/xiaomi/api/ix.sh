{% extends '//die/proxy.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/xapi
{% include 'xapi.py/base64' %}
EOF
chmod +x ${out}/bin/xapi
{% endblock %}
