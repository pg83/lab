{% extends '//lab/services/nebula/t/ix.sh' %}

{% block nebula_config %}
{{super()}}
lighthouse:
  am_lighthouse: false
  interval: 60
  hosts:
    - "192.168.100.1"
{% endblock %}
