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
73cb33a524d5332a4a35c43990cb66ab3e00469d2d38258c080b0ad00945bc32
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
# Fold submodule pins into the root before dropping them, or tidy — which
# walks every package in the collapsed module — resolves their imports to
# whatever upstream published today and the recorded hash rots.
find . -mindepth 2 -name go.mod | while read l; do
    awk '/^require \(/{r=1;next} r&&/^\)/{r=0;next} r' "${l}" |
        sed -n 's|^\t\([^ ]*\) \(v[^ ]*\).*|-require=\1@\2|p'
    sed -n 's|^require \([^ ]*\) \(v[^ ]*\).*|-require=\1@\2|p' "${l}"
done | sort -u | xargs -r -n 64 go mod edit
find . -mindepth 2 -name go.mod -delete
find . -mindepth 2 -name go.sum -delete
rm -f go.work go.work.sum
# Drop intra-repo require/replace lines after submodule collapse.
sed -i '/github\.com\/grafana\/grafana\//d' go.mod
{% endblock %}
