{% extends '//die/hub.sh' %}

{% block lib_deps %}
bin/clang/lib/cc
bin/clang/lib/ar
bin/clang/lib/ld
{% endblock %}

{% block run_deps %}
# TODO(pg): fix it
bin/clang/lib/cc
bin/clang/lib/ar
bin/clang/lib/ld
{% endblock %}
