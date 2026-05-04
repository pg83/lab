{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/event
{% include 'event.py/base64' %}
EOF

chmod +x ${out}/bin/event
{% endblock %}
