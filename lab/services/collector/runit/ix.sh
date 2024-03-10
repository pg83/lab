{% extends '//lab/services/persist/ix.sh' %}

{% block srv_command %}
cd /ix/realm/system/share
exec prometheus --config.file=/etc/prometheus.conf --storage.tsdb.path=/home/{{srv_user}}/
{% endblock %}
