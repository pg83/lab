{% extends '//die/c/autorehell.sh' %}

{% block fetch %}
http://jfs.sourceforge.net/project/pub/jfsutils-1.1.15.tar.gz
sha:244a15f64015ce3ea17e49bdf6e1a0fb4f9af92b82fa9e05aa64cb30b5f07a4d
{% endblock %}

{% block bld_libs %}
lib/c
lib/e2fsprogs
lib/shim/gnu/basename/overlay
{% endblock %}

{% block cpp_defines %}
_PATH_MNTTAB=\\\"/proc/mounts\\\"
{% endblock %}

{% block setup_target_flags %}
export CFLAGS="-fcommon ${CFLAGS}"
{% endblock %}

{% block patch %}
patch -p1 << EOF
{% include '0.diff' %}
EOF

patch -p1 << EOF
{% include '1.diff' %}
EOF
{% endblock %}
