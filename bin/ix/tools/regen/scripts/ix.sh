{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin ${out}/share/ix/regen
base64 -d << EOF > ${out}/share/ix/regen/libversion.py
{% include '//bin/repology/scripts/libversion.py/base64' %}
EOF
base64 -d << EOF > ${out}/bin/ix_flt
{% include 'flt.py/base64' %}
EOF
base64 -d << EOF > ${out}/bin/ix_repo
{% include 'repo.py/base64' %}
EOF
base64 -d << EOF > ${out}/bin/ix_regen
{% include 'urls/base64' %}
EOF
base64 -d << EOF > ${out}/bin/ix_urls_flt
{% include 'urls_flt.py/base64' %}
EOF
base64 -d << EOF > ${out}/bin/ix_repo_export
{% include 'repo_export.sh/base64' %}
EOF
base64 -d << EOF > ${out}/bin/ix_flt_upstream
{% include 'ix_flt_upstream.py/base64' %}
EOF
chmod +x ${out}/bin/*
{% endblock %}
