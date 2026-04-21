{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/share/grafana-provisioning/datasources

cat << EOF > ${out}/share/grafana-provisioning/datasources/prometheus.yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://127.0.0.1:{{collector_port | defined('collector_port')}}
    isDefault: true
EOF
{% endblock %}
