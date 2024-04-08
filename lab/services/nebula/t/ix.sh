{% extends '//etc/services/runit/script/ix.sh' %}

{% set cm = cluster_map | des %}

{% block srv_command %}
exec /bin/sh ${PWD}/run_nebula
{% endblock %}

{% block install %}
{{super()}}

cat << EOF > _
{% block nebula_config %}
pki:
  ca: ./ca.crt
  cert: ./host.crt
  key: ./host.key
{% endblock %}
EOF

base64 -d << EOF >> _
{% include 'config.yml/base64' %}
EOF

cat _ \
    | sed -e 's|4242|{{cm.ports.nebula}}|' \
    | sed -e 's|nebula_tun|nb{{nebula_host}}|' \
    > config.yaml

rm _

cat << EOF > run_nebula
etcdctl get --print-value-only /nebula/ca.crt > ca.crt
etcdctl get --print-value-only /nebula/{{nebula_host}}.crt > host.crt
etcdctl get --print-value-only /nebula/{{nebula_host}}.key > host.key
exec nebula --config=${PWD}/config.yaml
EOF
{% endblock %}
