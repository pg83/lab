{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/minio_iam_reconcile
{% include 'minio_iam_reconcile.py/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
