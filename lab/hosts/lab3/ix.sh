{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/hosts/lab3/mount
#lab/services/ci(ci_targets=set/ci/tier/1,wd=/var/mnt/home/ci)
{% endblock %}
