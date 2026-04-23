{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
mkdir -p ${out}/etc/cron

base64 -d << EOF > ${out}/bin/job_scheduler
{% include 'scheduler.py/base64' %}
EOF

chmod +x ${out}/bin/*
{% endblock %}
