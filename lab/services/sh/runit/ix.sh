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

{# Bake the resolved uid of every runtime pkg into run_sh as a
   comment. intro(p) loads the package without making it our dep,
   so its store hash flows into our own template render — but no
   pkg lands twice in the realm with conflicting flags. A bump of
   any of them changes run_sh content; pid1 sees the diff and
   restarts. #}
{% if extra_deps %}
{% for d in (extra_deps | b64d).split('\n') if d %}
echo '# dep-uid {{intro(d).uid}}' >> run_sh
{% endfor %}
{% endif %}
{% endblock %}
