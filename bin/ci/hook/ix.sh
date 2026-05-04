{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/etc/ogorod/ix

cat << 'EOF' > ${out}/etc/ogorod/ix/ci.sh
#!/bin/sh
set -e
sha="$1"

for tier in 0 1 2; do
    gorn ignite \
        --api "$GORN_API" \
        --root ci \
        --guid "set-tier-$tier-$sha" \
        --env "GORN_API=$GORN_API" \
        --env "S3_ENDPOINT=$S3_ENDPOINT" \
        --env "AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID_CIX" \
        --env "AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY_CIX" \
        --env "ETCDCTL_ENDPOINTS=$ETCDCTL_ENDPOINTS_PERSIST" \
        --env "MOLOT_QUIET=1" \
        --env "MOLOT_FULL_SLOTS=10" \
        -- /bin/env PATH=/bin ci check "set/ci/tier/$tier" "$sha"
done
EOF

chmod +x ${out}/etc/ogorod/ix/ci.sh
{% endblock %}
