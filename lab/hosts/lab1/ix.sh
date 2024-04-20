{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/hosts/lab1/mount
lab/services/ci(ci_targets=set/ci,wd=/var/mnt/home/ci)
{% endblock %}
