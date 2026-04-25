{% extends '//aux/fetch/ix.sh' %}

{# Lab shadow of upstream aux/go/v3. Difference: each `go mod tidy
   + go mod vendor` runs first via the cluster SOCKS5 proxy
   (localhost:8015 — the SshTunnel chain that also feeds stalix
   fetcher), and only if that fails — falls back to a direct
   attempt without proxy. So a flapping proxy can't permanently
   block builds, and a flapping Google modproxy can't either. #}

{% block fname %}
go_v3_{{parent_id}}.pzd
{% endblock %}

{% block bld_tool %}
{{go_tool | b64d}}
{{super()}}
{% endblock %}

{% block build %}
export GOSUMDB=off
export GOWORK=off
export GOCACHE=${tmp}/cgo
export GOMODCACHE=${tmp}/gmc
export GOPROXY="https://proxy.golang.org|direct"

go_fetch() {
    if HTTPS_PROXY=socks5://127.0.0.1:8015 HTTP_PROXY=socks5://127.0.0.1:8015 \
            go mod tidy \
       && HTTPS_PROXY=socks5://127.0.0.1:8015 HTTP_PROXY=socks5://127.0.0.1:8015 \
            go mod vendor; then
        return 0
    fi

    echo "go_fetch: socks5://127.0.0.1:8015 path failed, retrying direct" >&2
    go mod tidy && go mod vendor
}

{% if go_refine %}
{{go_refine | b64d}}
{% endif %}

find . -type f -name go.mod | while read l; do (
    cd $(dirname ${l})
    go_fetch
) done
{% endblock %}
