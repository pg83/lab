{% extends '//die/gen.sh' %}

{% block run_deps %}
bin/python
bin/openssh/client
{% endblock %}

{% block install %}
mkdir -p ${out}/bin ${out}/share/evac-view
base64 -d << EOF > ${out}/bin/evac-view
{% include 'view.py/base64' %}
EOF
{% for name in ['index.html', 'app.js', 'style.css'] %}
base64 -d << EOF > ${out}/share/evac-view/{{name}}
{% include name ~ '/base64' %}
EOF
{% endfor %}
chmod +x ${out}/bin/evac-view
{% endblock %}
