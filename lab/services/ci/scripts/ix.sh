{% extends '//die/gen.sh' %}

{% block install %}
mkdir ${out}/bin

cat << EOF > ${out}/bin/ci_cycle
#!/usr/bin/env sh

set -xue

export PATH=/bin:/ix/realm/boot/bin
export IX_ROOT=/ix

# Dispatch the build via molot → gorn → workers instead of running
# assemble locally. Artifacts land at
#   s3://\${S3_BUCKET}/molot/<molot-hash>-<uid>/result.zstd
# and the gorn control API (\${GORN_API}) orchestrates everything.
# GORN_API, S3_ENDPOINT, AWS_* come from the CI service env.
export IX_EXEC_KIND=molot
export S3_BUCKET=gorn

sleep 10

gpull https://github.com/pg83/ix ix

cd ix

./ix build {{ci_targets}} --seed=1

timeout 60s etcdctl watch --prefix /git/logs/git_ci | gnugrep --line-buffered 'PUT' | head -n 1
EOF

chmod +x ${out}/bin/*
{% endblock %}
