{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/etc
lab/common
lab/hosts/{{hostname}}
lab/services/autoupdate(user=ix)
{% endblock %}
