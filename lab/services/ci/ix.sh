{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/clone
bin/python
bin/gnugrep
lab/services/ci/unwrap(user=ci)
{% endblock %}
