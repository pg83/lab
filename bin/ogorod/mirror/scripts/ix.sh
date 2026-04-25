{% extends '//die/gen.sh' %}

{# Per repo each tick: ls-remote both upstream and our mirror_<r>,
   sort, compare. On equality (the common case at 10s cadence) we
   exit without touching the cache or doing a fetch — the whole
   tick is just six cheap HTTPS round-trips.

   On divergence: clone --bare on first run, fetch +heads/* +tags/*
   thereafter, push --mirror to the local ogorod_serve. Cache lives
   in /var/run/ogorod_mirror/cache/<r>; survives ticks, wiped on
   reboot — first tick post-boot re-clones from upstream. #}

{% block install %}
mkdir ${out}/bin

cat << 'EOF' > ${out}/bin/ogorod_mirror
#!/bin/sh
set -eu

REPOS="molot gorn ix lab samogon ogorod"
TARGET="http://127.0.0.1:8035"
CACHE="/var/run/ogorod_mirror/cache"

mkdir -p "${CACHE}"

for r in ${REPOS}; do
    src="https://github.com/pg83/${r}.git"
    dst="${TARGET}/mirror_${r}.git"

    src_refs=$(git ls-remote "${src}" 'refs/heads/*' 'refs/tags/*' | sort)
    dst_refs=$(git ls-remote "${dst}" 'refs/heads/*' 'refs/tags/*' | sort)

    if [ "${src_refs}" = "${dst_refs}" ]; then
        continue
    fi

    dir="${CACHE}/${r}"

    if [ ! -d "${dir}" ]; then
        echo "ogorod-mirror: cloning ${r}"
        git clone --bare "${src}" "${dir}"
    else
        echo "ogorod-mirror: fetching ${r}"
        git --git-dir="${dir}" fetch --prune origin \
            '+refs/heads/*:refs/heads/*' \
            '+refs/tags/*:refs/tags/*'
    fi

    echo "ogorod-mirror: pushing ${r} -> mirror_${r}"
    git --git-dir="${dir}" push --mirror "${dst}"
done
EOF

chmod +x ${out}/bin/*
{% endblock %}
