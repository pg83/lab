{% extends '//die/go/base.sh' %}

{% block step_unpack %}
mkdir src; cd src
base64 -d << EOF> cgi.go
{% include 'cgi.go/base64' %}
EOF
{% endblock %}

{% block go_build_flags %}
cgi.go
{% endblock %}

{% block install %}
mkdir ${out}/bin
cp cgi ${out}/bin/cgi_server
{% endblock %}
