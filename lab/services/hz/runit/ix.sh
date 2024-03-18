{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_command %}
while true; do
    sleep 100
    echo 'hz has been saved' >> hz
done
{% endblock %}
