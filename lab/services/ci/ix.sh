{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/bash
bin/clone
bin/python
bin/gnugrep
lab/services/ci/unwrap(user=ci,wd=/home/ci)
{% endblock %}
