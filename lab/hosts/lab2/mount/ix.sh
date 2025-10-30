{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

cat << EOF > ${out}/bin/mount_ci
#!/usr/bin/env sh
set -xue
mkdir -p \${1}
mount LABEL=CI \${1}
EOF

chmod +x ${out}/bin/*
{% endblock %}
