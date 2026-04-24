{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin

cat << EOF > ${out}/bin/ix
#!/usr/bin/env sh
exec /var/run/autoupdate_ix/ix/ix "\${@}"
EOF

base64 -d << EOF > ${out}/bin/autoupdate_cycle
{% include 'autoupdate.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
