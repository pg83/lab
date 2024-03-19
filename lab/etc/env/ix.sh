{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/env.d

cat << EOF > ${out}/etc/env.d/100-etcd
export ETCDCTL_ENDPOINTS="{{(cluster_map | des).etcd.ep}}"
EOF
{% endblock %}
