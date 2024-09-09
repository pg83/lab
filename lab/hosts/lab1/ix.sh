{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/devlink
lab/hosts/lab1/mount
lab/services/ci(ci_targets=set/ci,wd=/var/mnt/ci/ci)
{% endblock %}
