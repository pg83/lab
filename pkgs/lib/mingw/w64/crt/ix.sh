{% extends '//lib/mingw/w64/t/ix.sh' %}

{% block lib_deps %}
lib/mingw/w64/headers
lib/mingw/w64/pthreads
{% endblock %}

{% block unpack %}
{{super()}}
cd mingw-w64-crt
{% endblock %}

{% block configure_flags %}
{{super()}}
{% if x86_64 %}
--disable-lib32
--enable-lib64
{% else %}
--disable-lib64
--enable-lib32
{% endif %}
{% endblock %}

{% block build_flags %}
shut_up
{% endblock %}

{% block bld_tool %}
bin/binutils(for_target={{target.gnu.three}})
{% endblock %}

{% block install %}
{{super()}}
cd ${out}/lib
llvm-ar q libmingwcrt.a *.o
for x in atexit strtold; do
    llvm-objcopy --redefine-sym ${x}=${x}_1 libmsvcr120.a
    llvm-objcopy --redefine-sym ${x}=${x}_2 libmsvcr120_app.a
    llvm-objcopy --redefine-sym ${x}=${x}_3 libmsvcr120d.a
done
{% endblock %}
