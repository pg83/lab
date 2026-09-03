{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/profile.d

cat << EOF > ${out}/etc/profile.d/100-etcd
export ETCDCTL_ENDPOINTS="127.0.0.1:8020"
export MC_HOST_minio=http://qwerty:qwerty123@127.0.0.1:8012
export GORN_API=http://127.0.0.1:8025
export GORN_API_NB=http://{{hostname}}.nebula:8027
EOF
{% endblock %}
