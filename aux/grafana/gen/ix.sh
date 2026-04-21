{% extends '//die/gen.sh' %}

{% block fix_deps %}
["bld/python"]
{% endblock %}

{% block install %}
mkdir -p ${out}/bin
mkdir -p ${out}/fix

base64 -d << EOF > ${out}/bin/grafana_gen
{% include 'gen.py/base64' %}
EOF

chmod +x ${out}/bin/grafana_gen

cat << 'EOF' > ${out}/fix/50-grafana-gen.sh
set -xue
grafana_gen
EOF
{% endblock %}
