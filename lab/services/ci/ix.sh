{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/gorn
bin/molot
bin/python
bin/devlink
bin/su/exec
bin/git/clone
lab/services/ci/scripts
{% endblock %}
