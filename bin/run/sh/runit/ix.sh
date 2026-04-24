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
   so its store hash flows into our template render — but no pkg
   ever lands in the realm twice with conflicting flags from
   different services. When any runtime pkg moves, run_sh's
   content changes, the store path changes, pid1 sees the diff
   and restarts.

   The leading printf is load-bearing: gen_runner emits a single
   `exec runpy <ctx> ${@}` line WITHOUT a trailing newline, so
   the first echo would glue '# dep-uid X' onto the same word and
   sh would treat the # as part of expansion (not a comment) →
   extra positional args reach runpy → TypeError. Force the
   newline explicitly. #}
{% if extra_deps %}
printf '\n' >> run_sh
{% for d in (extra_deps | b64d).split('\n') if d %}
echo '# dep-uid {{intro(d).uid}}' >> run_sh
{% endfor %}
{% endif %}
{% endblock %}
