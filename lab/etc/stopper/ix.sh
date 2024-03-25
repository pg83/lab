{% extends '//die/proxy.sh' %}

{% block install %}
mkdir ${out}/fix
cat << EOF > ${out}/fix/99_disable_{{srv_dir | defined('srv_dir')}}.sh
rm -r etc/services/{{srv_dir}}
EOF
{% endblock %}
