{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/vault
set/stalix
bin/kernel/6/7
bin/kernel/6/6
bin/kernel/gengrub
bin/dropbear/runit
lab/autoupdate(user=ix)
{% endblock %}
