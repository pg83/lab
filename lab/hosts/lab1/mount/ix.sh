{% extends '//die/proxy.sh' %}

{% block install %}
mkdir ${out}/bin

cat << EOF > ${out}/bin/mount_ci
#!/usr/bin/env sh
set -xue
mkdir -p \${1}
devlink
mount -t bcachefs /dev/sda:/dev/links/40a63ab3-62f3-43dd-843f-fbed27622bf2:/dev/links/6ce93586-ad55-4248-bb21-d23eac83dbff:/dev/links/7965901e-abed-4628-92f2-a1a4194e6d1c \${1}
EOF

chmod +x ${out}/bin/*
{% endblock %}
