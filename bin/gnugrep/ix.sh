{% extends '//bin/grep/ix.sh' %}

{% block install %}
{{super()}}
cd ${out}
mv bin old
mkdir bin
mv old/grep bin/gnugrep
rm -rf old share
{% endblock %}
