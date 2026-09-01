{% extends '//die/gen.sh' %}

{% set cm = cluster_map | des %}

{% block install %}
mkdir -p ${out}/etc/profile.d

cat << EOF > ${out}/etc/profile.d/100-etcd
export ETCDCTL_ENDPOINTS="127.0.0.1:8020"
export MC_HOST_minio=http://qwerty:qwerty123@127.0.0.1:8012
export GORN_API=http://127.0.0.1:8025
export GORN_API_NB=http://{{hostname}}.nebula:8027
export IX_PACKAGE_CACHE="{% for host in cm.hosts %}{% for net in host.net %}{{net.ip}}:{{cm.ports.molot_cache}}{% if not (loop.last and host == cm.hosts[-1]) %},{% endif %}{% endfor %}{% endfor %}"
EOF
{% endblock %}
