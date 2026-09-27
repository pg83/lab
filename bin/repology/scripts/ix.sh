{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin ${out}/share/repology/overlay ${out}/share/repology/lib ${out}/share/repology/shims/libversion ${out}/share/repology/shims/pydantic

base64 -d << EOF > ${out}/bin/repology
{% include 'repology.py/base64' %}
EOF

chmod +x ${out}/bin/repology

base64 -d << EOF > ${out}/share/repology/lib/badge.py
{% include 'badge.py/base64' %}
EOF

base64 -d << EOF > ${out}/share/repology/overlay/http.py
{% include 'overlay_http.py/base64' %}
EOF

base64 -d << EOF > ${out}/share/repology/shims/libversion/__init__.py
{% include 'libversion.py/base64' %}
EOF

base64 -d << EOF > ${out}/share/repology/shims/xxhash.py
{% include 'xxhash.py/base64' %}
EOF

base64 -d << EOF > ${out}/share/repology/shims/yarl.py
{% include 'yarl.py/base64' %}
EOF

base64 -d << EOF > ${out}/share/repology/shims/jsonslicer.py
{% include 'jsonslicer.py/base64' %}
EOF

touch ${out}/share/repology/shims/pydantic/__init__.py

base64 -d << EOF > ${out}/share/repology/shims/pydantic/dataclasses.py
{% include 'pydantic_dataclasses.py/base64' %}
EOF

base64 -d << EOF > ${out}/share/repology/shims/pydantic/json.py
{% include 'pydantic_json.py/base64' %}
EOF
{% endblock %}
