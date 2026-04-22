{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/persdb
{% include 'persdb.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
