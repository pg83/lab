{% extends '//die/go/build.sh' %}

{% block go_url %}
https://github.com/pg83/kv/archive/refs/tags/3.tar.gz
{% endblock %}

{% block go_sha %}
ca0bbefeb0508f7df997b272e30f43c34083b3b3ed7c180c6efe4bbb03c77a68
{% endblock %}

{% block go_bins %}
kv
{% endblock %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}
