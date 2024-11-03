{% extends '//aux/ca/bundle/ix.sh' %}

{% block install %}
{{super()}}
find ${out}
mkdir -p ${out}/etc/ssl
cp ${out}/share/ssl/c* ${out}/etc/ssl/cert.pem
{% endblock %}
