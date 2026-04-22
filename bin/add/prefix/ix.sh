{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin

cat << 'EOF' > ${out}/bin/add_prefix
#!/bin/sh
# add_prefix PREFIX
#
# Read lines from stdin, write "<PREFIX><line>" to stdout. Line-buffered
# (fflush) so it chains cleanly inside pipelines feeding tinylog/Loki.
#
# Usage:
#     (smartctl -a /dev/sda) | add_prefix 'smart/sda: '
#     (ip rule list)         | add_prefix 'iprule: '
exec awk -v p="$1" '{print p $0; fflush()}'
EOF

chmod +x ${out}/bin/add_prefix
{% endblock %}
