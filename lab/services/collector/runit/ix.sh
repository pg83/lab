{% extends '//lab/services/persist/ix.sh' %}

{% set cm = cluster_map | des %}

{% block srv_command %}
cd /ix/realm/system/share
exec prometheus \
    --config.file=/etc/prometheus.conf \
    --storage.tsdb.path=/home/{{srv_user}}/ \
    --web.listen-address="0.0.0.0:{{cm.ports.prometheus}}"
{% endblock %}
