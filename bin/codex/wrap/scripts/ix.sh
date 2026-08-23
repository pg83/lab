{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin

cat << 'EOF' > ${out}/bin/codex
#!/usr/bin/env sh

if [ -z "${TMPDIR:-}" ] || [ ! -d "$TMPDIR" ] || [ ! -w "$TMPDIR" ]; then
    TMPDIR=/dev/shm
    export TMPDIR
fi

exec wirez -q -F 127.0.0.1:8015 -B 192.0.0.0/8 -- codex.exe "$@"
EOF

chmod +x ${out}/bin/codex
{% endblock %}
