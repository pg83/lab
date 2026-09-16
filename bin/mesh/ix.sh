{% extends '//die/go/build.sh' %}

{% block go_url %}
https://github.com/pg83/mesh/archive/refs/tags/31.tar.gz
{% endblock %}

{% block go_sha %}
fba9d2d4ba982cf32be77be26dd3b458098f961c4ba16a69e5370b2dd9c6a260
{% endblock %}

{% block go_bins %}
mesh
{% endblock %}

{% block go_tool %}
bin/go/lang/26
{% endblock %}
