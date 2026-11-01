{% extends '//die/go/build.sh' %}

{% block go_tool %}
bin/go/lang/25
{% endblock %}

{% block go_url %}
https://github.com/pg83/gorn/archive/refs/tags/38.tar.gz
{% endblock %}

{% block go_sha %}
1517642e10a2a68f3ab4538cbf2f796d66e35f32f3ccdcae29ccd54f322f72f0
{% endblock %}

{% block go_bins %}
gorn
{% endblock %}
