{% extends '//mix/template/make.sh' %}

{% block fetch %}
# url https://common-lisp.net/project/ecl/static/files/release/ecl-21.2.1.tgz
# md5 0c9e0437dbf3a7f1b00da32b7794a3b0
{% endblock %}

{% block deps %}
# bld lib/boehmgc/package.sh
# bld lib/gmp/package.sh
# bld lib/ffi/package.sh
# bld dev/build/make/package.sh
# bld env/std/package.sh
{% endblock %}

{% block postunpack %}
mkdir build && cd build
{% endblock %}

{% block configure %}
dash ../src/configure ${COFLAGS} \
    --enable-threads=yes \
    --enable-libatomic=system \
    --enable-gmp=system \
    --with-gmp-prefix=$lib_gmp \
    --with-libffi-prefix=$lib_ffi \
    --enable-boehm=yes \
    --with-libgc-prefix=$lib_boehmgc \
    --disable-shared \
    --enable-static \
    --prefix=${out} \
    --srcdir="${PWD}/../src"
{% endblock %}
