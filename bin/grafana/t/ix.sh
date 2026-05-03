{% extends '//die/go/build.sh' %}

{% block pkg_name %}
grafana
{% endblock %}

{% block version %}
13.0.1
{% endblock %}

{% block go_url %}
https://github.com/grafana/grafana/archive/refs/tags/v{{self.version().strip()}}.tar.gz
{% endblock %}

{% block go_sha %}
cc8f04f24b8c30768988e13de75c40e96022830495ceb1092b5d44f3cc431c82
{% endblock %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}

{% block go_refine %}
# Collapse go.work into a single module so aux/go/v3 mod-tidy works.
find . -type d -name testdata -prune -exec rm -rf {} +
find . -name '*_test.go' -delete
find . -mindepth 2 -name go.mod -delete
find . -mindepth 2 -name go.sum -delete
rm -f go.work go.work.sum
# Drop intra-repo require/replace lines after submodule collapse.
sed -i '/github\.com\/grafana\/grafana\//d' go.mod
{% endblock %}
