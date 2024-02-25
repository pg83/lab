{% extends '//die/proxy.sh' %}

{% block bld_tool %}
bin/busybox
{% endblock%}

{% block install %}
cd ${out}

mkdir -p etc/passwd.d

cat << EOF > etc/passwd.d/{{user or error()}}
{{user}}:{{hash or error()}}:{{userid or error()}}:{{userid}}:none:/home/{{user}}:{{login_shell or '/bin/sh'}}
EOF

mkdir -p etc/group.d

cat << EOF > etc/group.d/{{user}}
{{user}}:x:{{userid}}:
EOF

{% if pubkey %}
mkdir -p etc/sud.d

cat << EOF > etc/sud.d/{{user}}
{{pubkey}}
EOF
{% endif %}
{% endblock %}
