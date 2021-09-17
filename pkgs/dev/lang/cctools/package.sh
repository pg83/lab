{% extends '//util/autohell.sh' %}

{% block fetch %}
# url https://github.com/tpoechtrager/cctools-port/archive/236a426c1205a3bfcf0dbb2e2faf2296f0a100e5.zip
# md5 3ba3b9f5e6ebc2afe77cdafeaaeeb981
{% endblock %}

{% block deps %}
# bld lib/cxx
# bld dev/build/make env/c env/tools env/bootstrap
{% endblock %}

{% block cflags %}
export CPPFLAGS="-D__crashreporter_info__=__crashreporter_info_ld__ ${CPPFLAGS}"
{% endblock %}

{% block patch %}
sed -e 's/__arm__/__eat_shit__/' -i configure
{% endblock %}

{% block coflags %}
--with-sysroot=$OSX_SDK
{% endblock %}

{% block build %}
make -j ${make_thrs} || touch ld64/src/other/ObjectDump
{% endblock %}
