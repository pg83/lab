{% extends '//lab/services/nebula/t/ix.sh' %}

{% set cm = cluster_map | des %}

{% block nebula_config %}
{{super()}}
lighthouse:
  am_lighthouse: false
  interval: 60
  hosts:
{% for h in cm.hosts %}
{% if h.nebula.lh %}
    - "{{h.nebula.lh.vip}}"
{% endif %}
{% endfor %}
{% endblock %}
