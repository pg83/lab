{% extends '//die/go/pure.sh' %}

{% block go_url %}
https://github.com/antonmedv/llama/archive/refs/tags/v1.4.0.tar.gz
{% endblock %}

{% block go_sha %}
f0011b346cee13c231a76bc8ee6baef41b3cbd43f0ddc0780b50041ac4e1d4cf
{% endblock %}

{% block install %}
mkdir ${out}/bin
cp llama ${out}/bin/
{% endblock %}
