{% extends '//die/go/build.sh' %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}

{% block go_url %}
https://github.com/pg83/gorn/archive/refs/tags/27.tar.gz
{% endblock %}

{% block go_sha %}
c4bbe4bf4e77d03e49430f0c7c8bb3bc6d397d9331e61f01a0306a23d2cfe650
{% endblock %}

{% block go_bins %}
gorn
{% endblock %}
