{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/efi_del
{% include 'efi_del.sh/base64' %}
EOF
base64 -d << EOF > ${out}/bin/efi_get
{% include 'efi_get.sh/base64' %}
EOF
base64 -d << EOF > ${out}/bin/efi_put
{% include 'efi_put.sh/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
