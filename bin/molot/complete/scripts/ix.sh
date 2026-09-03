{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin

base64 -d << EOF > ${out}/bin/molot_complete
{% include 'molot_complete.py/base64' %}
EOF

chmod +x ${out}/bin/molot_complete
{% endblock %}
