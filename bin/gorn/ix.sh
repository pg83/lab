{% extends '//die/go/build.sh' %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}

{% block go_url %}
https://github.com/pg83/gorn/archive/refs/tags/27.tar.gz
{% endblock %}

{% block go_sha %}
3a004996aa5a869193319398ec2e18ba40b38d1342d14123422918c163a5ce82
{% endblock %}

{% block go_bins %}
gorn
{% endblock %}
