{% extends '//die/hub.sh' %}

{% set cluster_gen %}
{% include 'cg.py' %}
{% endset %}

{% set cluster_map | eval(cluster_gen) %}
{% include 'cg.py' %}
{% endset %}

{% block run_deps %}
lab/map(cluster_map={{cluster_map | ser}})
{% endblock %}
