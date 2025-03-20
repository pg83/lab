{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/env.d

cat << EOF > ${out}/etc/env.d/100-etcd
export ETCDCTL_ENDPOINTS="lab1.nebula:8020,lab2.nebula:8020,lab3.nebula:8020"
export MC_HOST_minio=http://qwerty:qwerty123@{{hostname}}.eth1:8012
EOF
{% endblock %}
