{% extends '//die/proxy.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/gclone
{% include 'clone.sh/base64' %}
EOF

base64 -d << EOF > ${out}/bin/gwait
{% include 'clone.sh/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
