{% extends '//die/c/autorehell.sh' %}

{% block fetch %}
https://gitlab.com/mbunkus/mkvtoolnix/-/archive/release-76.0/mkvtoolnix-release-76.0.tar.bz2
sha:274babfc46c4bdbd5886470477af3a4a51d5a6c6a3da4583d3e27d91933d73bf
{% endblock %}

{% block bld_libs %}
lib/c
lib/z
lib/gmp
lib/fmt
lib/ebml
lib/cmark
lib/boost
lib/pugixml
lib/matroska
lib/utf8/cpp
lib/xiph/ogg
lib/qt/6/svg
lib/qt/6/base
lib/xiph/vorbis
lib/json/nlohmann/11
lib/shim/fake(lib_name=stdc++)
{% endblock %}

{% block bld_tool %}
bld/ruby
bld/qt/6
bld/gettext
bld/fake/er(tool_name=xsltproc)
{% endblock %}

{% block configure_flags %}
--enable-static-qt
--with-qmake6=ixqmake6
--with-docbook_xsl_root=${out}
{% endblock %}

{% block setup_tools %}
mkdir QT

echo "${QT_PATH}" | tr ':' '\n' | while read l; do
    cp -R ${l}/* QT/
done

qqq=$(dirname $(dirname $(which qmake6)))

cp -R ${qqq}/* QT/

cd QT
ln -s bin libexec
cd ..

cat << EOF > qt.conf
[Paths]
Prefix = ${PWD}/QT
EOF

cat qt.conf

cat << EOF > ixqmake6
#!/usr/bin/env sh
qmake6 -qtconf ${PWD}/qt.conf "\${@}"
EOF

chmod +x ixqmake6
{% endblock %}

{% block build %}
./drake -j ${make_thrs}
{% endblock %}

{% block install %}
./drake install
{% endblock %}
