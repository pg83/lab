{% extends '//mix/template/hub.sh' %}

{% block lib_deps %}
lib/c
lib/gcr
lib/gtk
lib/gmp
lib/glib
lib/xml2
lib/cairo
lib/handy
lib/soup/3
lib/nettle
lib/webkit
lib/secret
lib/dazzle
lib/sqlite3
lib/archive
lib/json/glib
lib/gdk/pixbuf

# drivers
lib/glib/networking/register

# drivers
lib/mesa/gl
lib/mesa/egl
lib/mesa/drivers/vulkan
lib/mesa/drivers/gl/zink
{% endblock %}
