{% extends '//lab/services/nebula/t/ix.sh' %}

{% set cm = cluster_map | des %}

{% block nebula_config %}
{{super()}}
lighthouse:
  am_lighthouse: false
  interval: 60
  hosts:
{% for h in cm.hosts %}
{% if 'nebula' in h %}
    - "{{h.nebula.lh.vip}}"
{% endif %}
{% endfor %}
{% endblock %}
