{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/devlinkinto
{% include 'devlink.py/base64' %}
EOF

base64 -d << EOF > ${out}/bin/devlink
{% include 'devlink.sh/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
