{% extends '//die/go/build.sh' %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}

{% block go_url %}
https://github.com/pg83/gorn/archive/refs/tags/39.tar.gz
{% endblock %}

{% block go_sha %}
93f58799ee850ed0881f4c8de084e5d5090873d3e638ad85fdd4a622366884e3
{% endblock %}

{% block go_bins %}
gorn
{% endblock %}
