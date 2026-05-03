{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_user_prepare %}
{{super()}}
sh ${PWD}/run_sh prepare
{% endblock %}

{% block srv_command %}
# Log the resolved run_sh store path for deploy-convergence tracking.
echo "deploy: run_sh=$(readlink -f ${PWD}/run_sh)"
exec sh ${PWD}/run_sh run
{% endblock %}

{% block install %}
{{super()}}
base64 -d << EOF > run_sh
{{runsh_script}}
EOF

{# Bake runtime pkg uids into run_sh; pkg moves trigger pid1 restart.
   Leading printf forces newline; gen_runner emits no trailing one. #}
{% if extra_deps %}
printf '\n' >> run_sh
{% for d in (extra_deps | b64d).split('\n') if d %}
echo '# dep-uid {{intro(d).uid}}' >> run_sh
{% endfor %}
{% endif %}
{% endblock %}
