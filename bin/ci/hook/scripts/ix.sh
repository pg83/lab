{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin
mkdir -p ${out}/etc/event/git

base64 -d << EOF > ${out}/bin/ci_hook
{% include 'ci_hook.py/base64' %}
EOF

cat << 'EOF' > ${out}/etc/event/git/ci.json
{"cmd": ["ci_hook"]}
EOF

chmod +x ${out}/bin/ci_hook
{% endblock %}
