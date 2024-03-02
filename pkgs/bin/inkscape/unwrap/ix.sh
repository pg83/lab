{% extends '//die/c/cmake.sh' %}

{% block git_repo %}
https://gitlab.com/inkscape/inkscape
{% endblock %}

{% block git_branch %}
INKSCAPE_1_3_2
{% endblock %}

{% block git_sha %}
cc724c88a6d35a6815ee3858c2cfe092a444fd0f220e533c34aafbde7f65fc1c
{% endblock %}

{% block git_version %}
v2
{% endblock %}

{% block bld_libs %}
lib/c
lib/c++
lib/cdr
lib/dbus
lib/intl
lib/jpeg
lib/xslt
lib/wp/g
lib/2geom
lib/pango
lib/cairo
lib/boost
lib/visio
lib/xml/2
lib/lcms/2
lib/gspell
lib/soup/2
lib/poppler
lib/boehmgc
lib/potrace
lib/gtk/3/mm
lib/readline
lib/harfbuzz
lib/freetype
lib/dbus/glib
lib/fontconfig
lib/image/magick
lib/gdk/pixbuf/svg
lib/double/conversion
{% endblock %}

{% block bld_tool %}
bin/gzip
bld/perl
bld/glib
bld/python
bld/gettext
bin/ragel/6
{% endblock %}

{% block cmake_flags %}
WITH_X11=OFF
{% endblock %}

{% block cpp_defines %}
_LIBCPP_ENABLE_CXX17_REMOVED_FEATURES=1
{% endblock %}

{% block cpp_missing %}
libxml/xmlmemory.h
{% endblock %}

{% block setup_target_flags %}
export CXXFLAGS="-Wno-register ${CXXFLAGS}"
{% endblock %}

{% block patch %}
sed -e 's|PAGE_SIZE|X_PAGE_SIZE|' -i src/attributes.cpp
sed -e 's|PAGE_SIZE|X_PAGE_SIZE|' -i src/attributes.h
sed -e 's|PAGE_SIZE|X_PAGE_SIZE|' -i src/object/sp-page.cpp
{% endblock %}
