{% extends '//lib/mpv/t/ix.sh' %}

{% block bld_libs %}
lib/lua
lib/mu/js
lib/wayland
lib/mesa/gl
lib/mesa/egl
lib/xkbcommon
lib/drivers/3d
lib/rubber/band
lib/vulkan/headers
{{super()}}
{% endblock %}

{% block bld_tool %}
{{super()}}
bld/wayland
{% endblock %}

{% block waf_flags %}
{{super()}}
--enable-javascript
{% endblock %}
