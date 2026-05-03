{% extends '//die/gen.sh' %}

{# UDP/TCP buf+softirq; zz- prefix wins concat over upstream quic.conf. #}

{% block install %}
mkdir -p ${out}/etc/sysctl.d

cat << EOF > ${out}/etc/sysctl.d/zz-link-join.conf
net.core.rmem_max = 33554432
net.core.wmem_max = 33554432
net.core.netdev_max_backlog = 30000
EOF
{% endblock %}
