{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

cat << EOF > ${out}/bin/mount_ci
#!/bin/sh
set -xue
mkdir -p \${1}
mount LABEL=HOME \${1}
#fstrim -v \${1}
EOF

chmod +x ${out}/bin/*
{% endblock %}
