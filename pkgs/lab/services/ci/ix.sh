{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/services/ci/unwrap(user={{user or 'ci'}},wd={{wd or '/home/ci'}})
{% endblock %}
