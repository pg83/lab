{% extends '//mix/template/autohell.sh' %}

{% block fetch %}
# url https://gmplib.org/download/gmp/gmp-6.2.1.tar.lz
# md5 03a31d8cbaf29d136252f8f38875ed82
{% endblock %}

{% block deps %}
# bld dev/build/make/package.sh
# bld dev/lang/m4/package.sh
# bld env/std/package.sh
{% endblock %}

{% block env %}
export COFLAGS="--with-gmp=${out} --with-libgmp-prefix=${out} \${COFLAGS}"
{% endblock %}
