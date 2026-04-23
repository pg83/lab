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
export MOLOT_CACHE=./cache

sleep 30

# gpull exits 7 when there are no new commits — set -e short-circuits
# the rest of this cycle, runit restarts us, next sleep+gpull. Only
# spend time on ./ix build when there's actually something new
# upstream.
gpull https://github.com/pg83/ix ix

cd ix

# molot leaves mc-molot-<N> workdirs in cwd; owning processes are
# long gone, their mount namespaces reaped with them. Sweep before
# the fresh build starts, or they accumulate indefinitely.
rm -rf mc-molot-*

./ix build {{ci_targets}} --seed=1
EOF

chmod +x ${out}/bin/*
{% endblock %}
