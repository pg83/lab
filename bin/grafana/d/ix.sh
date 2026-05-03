{% extends '//bin/grafana/t/ix.sh' %}

{% block unpack %}
{{super()}}
cd pkg/cmd/grafana
{% endblock %}

{% block go_bins %}
grafana
{% endblock %}

# -p 4 + GOGC=25: full -p OOMs the 28 GiB box on grafana's many pkgs.
{% block go_build_flags %}
{{super()}}
-p 4
{% endblock %}

{% block step_setup %}
{{super()}}
export GOGC=25
{% endblock %}
