{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_command %}
(
while true; do
    sleep 150
    echo 'hz has been saved'
    date
done
) > hz
{% endblock %}
