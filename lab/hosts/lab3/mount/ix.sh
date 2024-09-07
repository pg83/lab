{% extends '//lab/etc/mount/ix.sh' %}

{% block mount %}
mkdir -p /var/mnt/ci
mount LABEL=HOME /var/mnt/ci
{% endblock %}
