{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/ci_metrics
{% include 'ci_metrics.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
