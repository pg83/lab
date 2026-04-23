{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
lab/etc/user
bin/git/clone
lab/services/autoupdate/scripts
{% endblock %}
