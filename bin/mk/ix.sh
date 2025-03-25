{% extends '//die/hub.sh' %}

{% block run_deps %}
set/fs
bin/rsync
bin/grub/efi
bin/mk/scripts
{% endblock %}
