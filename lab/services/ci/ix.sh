{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/python
bin/gnugrep
bin/git/clone
lab/services/ci/unwrap(user=ci)
{% endblock %}
