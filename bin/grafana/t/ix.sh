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
cf8e1f22704605a25b79629691cbeaa3124cd474167eca4c9665b1301b5a1a84
{% endblock %}

{% block go_tool %}
bin/go/lang/26
{% endblock %}

{% block go_args %}
{{super()}}
refine_tools={{'bld/git' | b64e}}
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
