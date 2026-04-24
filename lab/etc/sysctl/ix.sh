{% extends '//die/gen.sh' %}

{# Overrides the ix-provided etc/sysctl.d/quic.conf (2.5 MiB) with a
   16 MiB ceiling. Needed so nebula's listen.read_buffer/write_buffer
   request of 8 MiB actually takes effect on setsockopt — anything
   above rmem_max/wmem_max clamps silently. See lab/NET.md. #}

{% block install %}
mkdir -p ${out}/etc/sysctl.d

cat << EOF > ${out}/etc/sysctl.d/quic.conf
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
EOF
{% endblock %}
