{% extends '//etc/services/runit/script/ix.sh' %}

{% block srv_command %}
exec gosmee client --saveDir \${PWD} --noReplay "{{evlog_url}}" qw >& events
{% endblock %}
