{% extends '//die/hub.sh' %}

{% block run_deps %}
lab/vault
bin/ix/ci
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
