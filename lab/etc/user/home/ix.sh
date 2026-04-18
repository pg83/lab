{% extends '//die/gen.sh' %}

{% block bld_tool %}
bin/busybox
{% endblock %}

{% set cm = cluster_map | des %}

{% block install %}
cd ${out}

mkdir -p etc/passwd.d

cat << EOF > etc/passwd.d/{{user | defined('user')}}
{{user}}:x:{{cm.users[user]}}:{{cm.users[user]}}:none:{{user_home | defined('user_home')}}:/bin/sh
EOF

mkdir -p etc/shells.d

cat << EOF > etc/shells.d/{{user}}
/bin/sh
EOF

mkdir -p etc/group.d

cat << EOF > etc/group.d/{{user}}
{{user}}:x:{{cm.users[user]}}:
EOF
{% endblock %}
