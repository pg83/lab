{% extends '//die/go/build.sh' %}

{% block go_url %}
https://github.com/pg83/kv/archive/refs/tags/1.tar.gz
{% endblock %}

{% block go_sha %}
106c7d8aea32bda50319aba820dcdea0d5b1d8e1568a71e56fe66e477ede611a
{% endblock %}

{% block go_bins %}
kv
{% endblock %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}
