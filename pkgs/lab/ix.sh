{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/mc
lab/etc
lab/vault
set/stalix
bin/kernel/6/7
bin/kernel/6/6
bin/kernel/gengrub
bin/dropbear/runit
{% if hostname %}
lab/hosts/{{hostname}}
{% endif %}
lab/autoupdate(user=ix)
{% endblock %}
