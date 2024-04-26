{% extends '//die/hub.sh' %}

{% block cluster_gen %}
{% include 'cg.py' %}
{% endblock %}

{% block run_deps %}
lab/map(cluster_map={{self.cluster_gen() | eval(self.cluster_gen()) | ser}},dev_mngr=fs)
{% endblock %}
