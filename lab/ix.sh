{% extends '//die/hub.sh' %}

{% block cluster_gen %}
{% include 'cg.py' %}
{% endblock %}

{% set cluster_map | eval(self.cluster_gen()) %}
{{self.cluster_gen()}}
{% endset %}

{% block run_deps %}
lab/map(cluster_map={{cluster_map | ser}})
{% endblock %}
