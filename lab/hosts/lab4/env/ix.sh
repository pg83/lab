{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/env.d
cat << EOF > ${out}/etc/env.d/101-minio
export MC_HOST_minio=http://qwerty:qwerty123@lab3.eth1:8012
EOF
{% endblock %}
