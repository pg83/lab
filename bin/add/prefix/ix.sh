{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin

cat << 'EOF' > ${out}/bin/add_prefix
#!/bin/sh
# add_prefix PREFIX: prepend PREFIX to each stdin line, line-buffered.
exec awk -v p="$1" '{print p $0; fflush()}'
EOF

chmod +x ${out}/bin/add_prefix
{% endblock %}
