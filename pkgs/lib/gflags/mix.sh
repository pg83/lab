{% extends '//die/cmake.sh' %}

{% block fetch %}
https://github.com/gflags/gflags/archive/refs/tags/v2.2.2.tar.gz
sha:34af2f15cf7367513b352bdcd2493ab14ce43692d2dcd9dfc499492966c64dcf
{% endblock %}

{% block lib_deps %}
lib/c
lib/c++
{% endblock %}

{% block install %}
{{super()}}
sed -e 's|.*bindir.*||' -i ${out}/lib/pkgconfig/gflags.pc
{% endblock %}
