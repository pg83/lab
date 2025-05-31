{% extends '//die/std/ix.sh' %}

{% block fetch %}
https://github.com/huggingface/huggingface_hub/archive/refs/tags/v0.32.3.tar.gz
sha:784b23a65767f721d7b9a5b10259da3ae326e69b41b6887be4aa3a56f84d541e
{% endblock %}

{% block install %}
mkdir ${out}/bin
cp -R src/huggingface_hub ${out}/bin/
base64 -d << EOF > ${out}/bin/huggingface_cli
{% include 'cli.sh/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
