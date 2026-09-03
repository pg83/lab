{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin
cat << EOF > ${out}/bin/cache_ix_sources
#!/usr/bin/env python3
P = '''
{{socks5_proxy}}
'''
EOF
base64 -d << EOF >> ${out}/bin/cache_ix_sources
{% include 'fetch.py/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
