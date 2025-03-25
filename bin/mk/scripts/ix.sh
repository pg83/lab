{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/lab_boot
{% include 'boot.sh/base64' %}
EOF
base64 -d << EOF > ${out}/bin/lab_install
{% include 'install.sh/base64' %}
EOF
base64 -d << EOF > ${out}/bin/lab_sync
{% include 'sync.sh/base64' %}
EOF
base64 -d << EOF > ${out}/bin/lab_sync_py
{% include 'sync.py/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
