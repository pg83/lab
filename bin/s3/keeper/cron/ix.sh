{% extends '//die/hub.sh' %}

{# The cluster cron runs the keeper: one round, queue a cell to compact or not. #}

{% block run_deps %}
bin/s3/keeper/cron/scripts(s3_config={{s3_config}})
bin/s3/store
{% endblock %}
