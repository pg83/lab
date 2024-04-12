{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_command %}
exec python3 ${PWD}/run_py
{% endblock %}

{% block install %}
{{super()}}
base64 -d << EOF > run_py
{{runpy_script}}
EOF
{% endblock %}