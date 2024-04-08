{% extends '//etc/services/runit/script/ix.sh' %}

{% set cm = cluster_map | des %}

{% block srv_command %}
exec /bin/sh ${PWD}/run_nebula
{% endblock %}

{% block install %}
{{super()}}

cat << EOF > config.yaml
{% block nebula_config %}
static_host_map:
{% for h in cm.hosts %}
{% if 'nebula' in h %}
  "{{h.nebula.lh.vip}}": ["{{h.nebula.lh.ip}}:{{h.nebula.lh.port}}", "{{h.ip}}:{{cm.ports.nebula_lh}}"]
{% endif %}
{% endfor %}

pki:
  ca: ./ca.crt
  cert: ./host.crt
  key: ./host.key

listen:
  host: 0.0.0.0
  port: {{nebula_port | defined('nebula_port')}}

tun:
{% if nebula_iface %}
  disabled: false
  dev: {{nebula_iface}}
  drop_local_broadcast: false
  drop_multicast: false
  tx_queue: 500
  mtu: 1300
{% else %}
  disabled: true
{% endif %}
{% endblock %}
EOF

base64 -d << EOF >> config.yaml
{% include 'config.yml/base64' %}
EOF

cat << EOF > run_nebula
etcdctl get --print-value-only /nebula/ca.crt > ca.crt
etcdctl get --print-value-only /nebula/{{nebula_host}}.crt > host.crt
etcdctl get --print-value-only /nebula/{{nebula_host}}.key > host.key
exec nebula --config=${PWD}/config.yaml
EOF
{% endblock %}
