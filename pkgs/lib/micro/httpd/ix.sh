{% extends '//die/c/autorehell.sh' %}

{% block fetch %}
https://ftp.gnu.org/gnu/libmicrohttpd/libmicrohttpd-1.0.0.tar.gz
sha:a02792d3cd1520e2ecfed9df642079d44a36ed87167442b28d7ed19e906e3e96
{% endblock %}

{% block lib_deps %}
lib/c
lib/curl
lib/iconv
lib/gnutls
{% endblock %}

{% block bld_tool %}
bld/texinfo
bld/gettext
{% endblock %}
