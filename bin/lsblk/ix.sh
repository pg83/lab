{% extends '//lib/linux/util/t/ix.sh' %}

{% block bld_libs %}
lib/c
lib/kernel
lib/sqlite/3
{% endblock %}

{% block configure_flags %}
{{super()}}
--disable-colors-default
--disable-makeinstall-chown
--disable-makeinstall-setuid
{% endblock %}

{% block make_target %}
lsblk
{% endblock %}

{% block install %}
mkdir ${out}/bin
cp lsblk ${out}/bin/
{% endblock %}
