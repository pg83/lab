{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

base64 -d << EOF > ${out}/bin/cluster_status
{% include 'cluster_status.sh/base64' %}
EOF

base64 -d << EOF > ${out}/bin/gen_gorn_keys
{% include 'gen_gorn_keys.sh/base64' %}
EOF

base64 -d << EOF > ${out}/bin/molot_trace
{% include 'molot_trace.sh/base64' %}
EOF

base64 -d << EOF > ${out}/bin/set_master_key
{% include 'set_master_key.sh/base64' %}
EOF

base64 -d << EOF > ${out}/bin/extract_nebula_secrets
{% include 'extract_nebula_secrets.py/base64' %}
EOF

base64 -d << EOF > ${out}/bin/iperf_serve
{% include 'iperf_serve.sh/base64' %}
EOF

base64 -d << EOF > ${out}/bin/iperf_shot
{% include 'iperf_shot.sh/base64' %}
EOF

base64 -d << EOF > ${out}/bin/log_follow
{% include 'log_follow.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
