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
base64 -d << EOF > ${out}/share/evac-view/index.html
{% include 'index.html/base64' %}
EOF
base64 -d << EOF > ${out}/share/evac-view/app.js
{% include 'app.js/base64' %}
EOF
base64 -d << EOF > ${out}/share/evac-view/style.css
{% include 'style.css/base64' %}
EOF
chmod +x ${out}/bin/evac-view
{% endblock %}
