{% extends '//boot/stage/8/bison/template/package.sh' %}

{% block fetch %}
# url https://ftp.gnu.org/gnu/bison/bison-3.6.1.tar.xz
# md5 16fa3e60f2c33888c6ef7af64c89e182
{% endblock %}

{% block bison %}
# bld boot/stage/8/bison/351/stage1/package.sh
# bld boot/stage/8/patch/package.sh
{% endblock %}

{% block patch %}
(base64 -d | patch -p0) << EOF
{% include 'bison.diff/base64' %}
EOF

rm src/parse-gram.c src/parse-gram.h
{% endblock %}

{% block bison_cflags %}
export CPPFLAGS="-DGRAM_error=1 ${CPPFLAGS}"
{% endblock %}
