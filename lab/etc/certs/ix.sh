{% extends '//aux/ca/bundle/ix.sh' %}

{% block install %}
{{super()}}
mkdir -p ${out}/etc/ssl
cp ${out}/share/ssl/ca-bundle.pem ${out}/etc/ssl/
{% endblock %}
