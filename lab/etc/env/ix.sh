{% extends '//die/proxy.sh' %}

{% block install %}
mkdir -p ${out}/etc/env.d

cat << EOF > ${out}/etc/env.d/100-etcd
export ETCDCTL_ENDPOINTS="lab1:2379,lab2:2379,lab3:2379"
EOF
{% endblock %}
