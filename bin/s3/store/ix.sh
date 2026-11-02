{% extends '//die/go/build.sh' %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}

{% block go_url %}
https://github.com/pg83/s3/archive/39.tar.gz
{% endblock %}

{% block go_sha %}
f267943cf9cc53235d03e23ace8fd5fdedbea7fe64ec1f843e93e43b8de41295
{% endblock %}

{% block go_bins %}
s3
{% endblock %}
