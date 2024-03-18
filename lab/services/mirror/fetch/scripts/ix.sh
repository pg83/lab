{% extends '//die/proxy.sh' %}

{% block install %}
cd ${out}; mkdir bin; cd bin

cat << EOF > fetch_ix_mirror
#!/usr/bin/env sh
set -xue
mkdir -p {{wd}}
cd {{wd}}
mkdir -p data
rm -rf ix-main main.zip
wget https://github.com/pg83/ix/archive/refs/heads/main.zip
unzip main.zip
cd ix-main
./ix recache {{wd}}/data || true
sleep 3600
EOF

chmod +x *
{% endblock %}
