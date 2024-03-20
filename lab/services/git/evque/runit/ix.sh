{% extends '//etc/services/runit/script/ix.sh' %}

{% block under_lock %}
set -xue
gosmee client --saveDir ${PWD} --noReplay "{{evlog_url}}" qw 2>&1 | gnugrep --line-buffered 'has been saved' | while read l; do
    cat *.json | etcdctl put /git/logs/{{evlog_user}}
    rm *.json *.sh
done
{% endblock %}

{% block install %}
{{super()}}
base64 -d << EOF > sh_script
{{self.under_lock() | b64e}}
EOF
{% endblock %}

{% block srv_command %}
set -xue
exec etcdctl lock /git/logs/{{evlog_user}} -- /bin/sh ${PWD}/sh_script
{% endblock %}
