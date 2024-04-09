{% extends '//die/go/base.sh' %}

{% block step_unpack %}
mkdir src
cd src
base64 -d << EOF > serve.go
{% include 'serve.go/base64' %}
EOF
{% endblock %}

{% block go_build_flags %}
serve.go
{% endblock %}

{% block install %}
mkdir ${out}/bin
cp serve ${out}/bin/http_serve
{% endblock %}
