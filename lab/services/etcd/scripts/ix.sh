{% extends '//die/proxy.sh' %}

{% block cluster_map %}
{{cluster_map | b64d}}
{% endblock %}

{% set my_ip %}{{(self.cluster_map() | jl | group_by("hostname"))[hostname][0]["ip"]}}{% endset %}

{% block all_etcd %}
{% for x in self.cluster_map() | jl %}
{{x["hostname"]}}=http://{{x["ip"]}}:2380
{% endfor %}
{% endblock %}

{% block etcd_conf %}
--name {{hostname}}
--initial-advertise-peer-urls http://{{my_ip}}:2380
--listen-peer-urls http://{{my_ip}}:2380
--listen-client-urls http://{{my_ip}}:2379,http://127.0.0.1:2379
--advertise-client-urls http://{{my_ip}}:2379
--initial-cluster-token etcd-cluster-1
--initial-cluster {{','.join(ix.parse_list(self.all_etcd()))}}
--initial-cluster-state new
{% endblock %}

{% block install %}
mkdir ${out}/bin

cat << EOF >> ${out}/bin/etcd_runner
#!/usr/bin/env sh
exec etcd {{ix.fix_list(self.etcd_conf())}}
EOF

chmod +x ${out}/bin/*
{% endblock %}
