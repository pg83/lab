{% extends '//die/hub.sh' %}

{% block run_deps %}
bin/rsync
bin/parted
bin/xfsprogs
bin/grub/efi
bin/dosfstools
bin/mk/scripts
{% endblock %}
