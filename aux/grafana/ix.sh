{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/share/grafana-provisioning/datasources
mkdir -p ${out}/share/grafana-provisioning/dashboards
mkdir -p ${out}/share/grafana-provisioning/dashboards-json

cat << EOF > ${out}/share/grafana-provisioning/datasources/prometheus.yaml
apiVersion: 1
datasources:
  - name: Prometheus
    uid: prom
    type: prometheus
    access: proxy
    url: http://127.0.0.1:{{collector_port | defined('collector_port')}}
    isDefault: true
EOF

cat << EOF > ${out}/share/grafana-provisioning/dashboards/cluster.yaml
apiVersion: 1
providers:
  - name: cluster
    folder: ''
    type: file
    disableDeletion: true
    allowUiUpdates: false
    updateIntervalSeconds: 30
    options:
      path: ${out}/share/grafana-provisioning/dashboards-json
      foldersFromFilesStructure: false
EOF

base64 -d << EOF > ${out}/share/grafana-provisioning/dashboards-json/cluster.json
{% include 'cluster.json/base64' %}
EOF
{% endblock %}
