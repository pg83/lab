{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
base64 -d << EOF > ${out}/bin/cache_ix_sources
{% include 'fetch.py/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
