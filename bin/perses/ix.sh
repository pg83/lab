{% extends '//die/go/build.sh' %}

{% block pkg_name %}
perses
{% endblock %}

{% block version %}
0.53.1
{% endblock %}

{% block go_url %}
https://github.com/perses/perses/archive/refs/tags/v{{self.version().strip()}}.tar.gz
{% endblock %}

{% block go_sha %}
8707946e2d6c4e5f9d96bed8255cfbb48005ca88df93b3f85513e17db217da67
{% endblock %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}

{% block bld_tool %}
{{super()}}
bld/gzip
{% endblock %}

{% block go_refine %}
# Drop testdata go.mod trees so aux/go/v3's mod-tidy stays on real modules.
find . -type d -name testdata -prune -exec rm -rf {} +
{% endblock %}

{% block unpack %}
{{super()}}
# Stub one-file ui/app/dist so cmd/perses compiles without compress_assets.sh.
(
    cd ui
    cp embed.go.tmpl embed.go
    mkdir -p app/dist
    printf '<!doctype html><meta charset=utf-8><title>Perses</title><p>UI not built (stal-ix source build).' > app/dist/index.html
    gzip -f app/dist/index.html
    printf '//go:embed app/dist/index.html.gz\nvar embedFS embed.FS\n' >> embed.go
)
cd cmd/perses
{% endblock %}

{% block go_bins %}
perses
{% endblock %}
