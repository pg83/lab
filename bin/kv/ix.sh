{% extends '//die/go/build.sh' %}

{% block go_url %}
https://github.com/pg83/kv/archive/refs/tags/2.tar.gz
{% endblock %}

{% block go_sha %}
b0a380ed567bda2f03af0cccf1eade954b3f01004817c5dbaa1385245a501e49
{% endblock %}

{% block go_bins %}
kv
{% endblock %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}
