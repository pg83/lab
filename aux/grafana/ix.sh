{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/share/grafana-provisioning/datasources
mkdir -p ${out}/share/grafana-provisioning/dashboards
mkdir -p ${out}/share/grafana-provisioning/dashboards-json

cat << EOF > ${out}/share/grafana-provisioning/datasources/datasources.yaml
apiVersion: 1
datasources:
  - name: Prometheus
    uid: prom
    type: prometheus
    access: proxy
    url: http://127.0.0.1:{{collector_port | defined('collector_port')}}
    orgId: 1
    isDefault: true
    editable: false
  - name: Loki
    uid: loki
    type: loki
    access: proxy
    url: http://127.0.0.1:{{loki_port | defined('loki_port')}}
    orgId: 1
    editable: false
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

base64 -d << EOF > ${out}/share/grafana-provisioning/dashboards-json/minio.json
{% include 'minio.json/base64' %}
EOF

base64 -d << EOF > ${out}/share/grafana-provisioning/dashboards-json/loki.json
{% include 'loki.json/base64' %}
EOF

base64 -d << EOF > ${out}/share/grafana-provisioning/dashboards-json/grafana.json
{% include 'grafana.json/base64' %}
EOF

base64 -d << EOF > ${out}/share/grafana-provisioning/dashboards-json/prometheus.json
{% include 'prometheus.json/base64' %}
EOF

base64 -d << EOF > ${out}/share/grafana-provisioning/dashboards-json/etcd.json
{% include 'etcd.json/base64' %}
EOF

base64 -d << EOF > ${out}/share/grafana-provisioning/dashboards-json/nebula.json
{% include 'nebula.json/base64' %}
EOF
{% endblock %}
