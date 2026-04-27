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
    url: {{prom_url | defined('prom_url')}}
    orgId: 1
    isDefault: true
    editable: false
  - name: Loki
    uid: loki
    type: loki
    access: proxy
    url: {{loki_url | defined('loki_url')}}
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

base64 -d << EOF > ${out}/share/grafana-provisioning/dashboards-json/ci.json
{% include 'ci.json/base64' %}
EOF

{# Per-service deploy convergence dashboard. One timeseries panel
   per service, two-column grid, value = distinct run_sh paths in
   the cluster — drops to 1 once all 3 hosts converged on the same
   /ix/store/<HASH> for that service's runit wrapper.

   services_b64 is a base64-encoded newline-joined list (comma-
   joined would collide with ix's k=v,k2=v2 package param
   syntax — same trick extra_deps uses). #}
{% set svc_list = (services_b64 | b64d).split('\n') | reject('equalto', '') | list %}
cat > ${out}/share/grafana-provisioning/dashboards-json/deploy.json <<'JSON'
{
  "uid": "deploy",
  "title": "Deploy convergence",
  "tags": ["deploy"],
  "schemaVersion": 39,
  "version": 1,
  "time": {"from": "now-30m", "to": "now"},
  "refresh": "30s",
  "templating": {"list": []},
  "panels": [
{% for svc in svc_list %}
{% set col = (loop.index0 % 2) * 12 %}
{% set row = (loop.index0 // 2) * 6 %}
    {"id": {{ loop.index }},
     "title": "{{ svc }}: distinct run_sh paths (1 = converged)",
     "type": "timeseries",
     "gridPos": {"h": 6, "w": 12, "x": {{ col }}, "y": {{ row }}},
     "datasource": {"type": "loki", "uid": "loki"},
     "fieldConfig": {"defaults": {
       "min": 0,
       "custom": {"drawStyle": "line", "lineInterpolation": "stepAfter", "fillOpacity": 8, "showPoints": "always", "pointSize": 4},
       "thresholds": {"mode": "absolute", "steps": [
         {"value": null, "color": "green"},
         {"value": 2, "color": "red"}
       ]}
     }},
     "options": {"legend": {"showLegend": false}, "tooltip": {"mode": "single"}},
     "targets": [
       {"refId": "A",
        "expr": "count(count by (path) (count_over_time({service=\"{{ svc }}\",stream=\"tinylog\"} |= `deploy: run_sh=` | regexp `deploy: run_sh=(?P<path>\\S+)` [5m])))",
        "legendFormat": "distinct paths"}
     ]}{% if not loop.last %},{% endif %}
{% endfor %}
  ]
}
JSON
{% endblock %}
