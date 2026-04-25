{% extends '//die/gen.sh' %}

{# Mirror six github repos into ogorod under mirror_<name>. Each
   tick: clone --bare on first run, fetch +refs/heads/* +refs/tags/*
   thereafter, push --mirror to the local ogorod_serve on 127.0.0.1.

   Cache lives in /var/run/ogorod_mirror/cache/<name>; survives
   between job_scheduler ticks but is wiped on reboot — first tick
   after boot re-clones from upstream. Network egress is small
   (incremental fetch); the heavy lifting on push --mirror is local. #}

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
    dir="${CACHE}/${r}"

    if [ ! -d "${dir}" ]; then
        echo "ogorod-mirror: cloning ${r}"
        git clone --bare "https://github.com/pg83/${r}.git" "${dir}"
    else
        echo "ogorod-mirror: fetching ${r}"
        git --git-dir="${dir}" fetch --prune origin \
            '+refs/heads/*:refs/heads/*' \
            '+refs/tags/*:refs/tags/*'
    fi

    echo "ogorod-mirror: pushing ${r} -> mirror_${r}"
    git --git-dir="${dir}" push --mirror "${TARGET}/mirror_${r}.git"
done
EOF

chmod +x ${out}/bin/*
{% endblock %}
