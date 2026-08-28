{% extends '//die/go/build.sh' %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}

{% block go_url %}
https://github.com/pg83/molot/archive/refs/tags/27.tar.gz
{% endblock %}

{% block go_sha %}
ba116773f442f058fb05bf8d0845ea664379470402302ac637cbcee0e83a9a5a
{% endblock %}

{% block go_bins %}
molot
{% endblock %}
