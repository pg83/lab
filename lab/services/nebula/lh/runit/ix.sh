{% extends '//lab/services/nebula/t/ix.sh' %}

{% block nebula_config %}
{{super()}}
lighthouse:
  interval: 60
  am_lighthouse: true
{% endblock %}
