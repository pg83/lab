{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin ${out}/share/updater

base64 -d << EOF > ${out}/bin/updater
{% include 'updater.py/base64' %}
EOF

base64 -d << EOF > ${out}/share/updater/libversion.py
{% include '//bin/repology/scripts/libversion.py/base64' %}
EOF

base64 -d << EOF > ${out}/share/updater/lines.py
{% include 'lines.py/base64' %}
EOF

chmod +x ${out}/bin/updater
{% endblock %}
