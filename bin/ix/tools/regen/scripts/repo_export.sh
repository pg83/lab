#!/usr/bin/env sh

set -xue
set -o pipefail

dump=pkgs/die/scripts/dump.json
pending=$(mktemp "${dump}.XXXXXX")
trap 'rm -f "${pending}"' EXIT

IX_EXEC_KIND=fake IX_DUMP_REPO=1 ./ix build set/ci --seed=1 \
    | ix_repo \
    | sort \
    | uniq \
    | ix_flt \
    | sort \
    | uniq \
    | grep -v nlua0 \
    | grep -v "bin/xxd" \
    > "${pending}"

mv "${pending}" "${dump}"
