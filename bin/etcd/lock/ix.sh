{% extends '//bin/etcd/t/ix.sh' %}

{% block unpack %}
{{super()}}

mkdir -p etcdctl/cmd/etcd_lock

base64 -d << EOF > etcdctl/cmd/etcd_lock/main.go
{% include 'main.go/base64' %}
EOF

base64 -d << EOF > etcdctl/cmd/etcd_lock/main_test.go
{% include 'main_test.go/base64' %}
EOF

cd etcdctl/cmd/etcd_lock
{% endblock %}

{% block go_build_flags %}
{{super()}}
-o=etcd_lock
.
{% endblock %}

{% block test %}
go test -mod=vendor .
{% endblock %}

{% block install %}
mkdir ${out}/bin
cp etcd_lock ${out}/bin/
{% endblock %}
