{% extends '//die/go/base.sh' %}

{% block run_deps %}
bin/bash
bin/git/unwrap
{% endblock %}

{% block step_unpack %}
mkdir src
cd src
base64 -d << EOF > batcher.go
{% include 'batcher.go/base64' %}
EOF
{% endblock %}

{% block step_setup %}
{{super()}}
export CGO_ENABLED=0
{% endblock %}

{% block go_build_flags %}
batcher.go
{% endblock %}

{% block install %}
mkdir ${out}/bin
cp batcher ${out}/bin/batcher
{% endblock %}
