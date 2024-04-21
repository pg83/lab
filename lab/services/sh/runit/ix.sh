{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_user_prepare %}
{{super()}}
sh ${PWD}/run_sh prepare
{% endblock %}

{% block srv_command %}
exec sh ${PWD}/run_sh run
{% endblock %}

{% block install %}
{{super()}}
base64 -d << EOF > run_sh
{{runsh_script}}
EOF
{% endblock %}
