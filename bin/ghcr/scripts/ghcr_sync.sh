#!/usr/bin/env sh

set -xue

echo ${PATH}

sleep 200

rm -rf _

minio-client ls minio/cas | grep STA | sed -e 's|.* ||' | sort | grep -v '^$' > 1

touch 2

(
    cat 2
    oras repo tags ghcr.io/stal-ix/pkgsrc/0
    oras repo tags ghcr.io/stal-ix/pkgsrc/1
    oras repo tags ghcr.io/stal-ix/pkgsrc/2
    oras repo tags ghcr.io/stal-ix/pkgsrc/3
    oras repo tags ghcr.io/stal-ix/pkgsrc/4
    oras repo tags ghcr.io/stal-ix/pkgsrc/5
    oras repo tags ghcr.io/stal-ix/pkgsrc/6
    oras repo tags ghcr.io/stal-ix/pkgsrc/7
    oras repo tags ghcr.io/stal-ix/pkgsrc/8
    oras repo tags ghcr.io/stal-ix/pkgsrc/9
    oras repo tags ghcr.io/stal-ix/pkgsrc/a
    oras repo tags ghcr.io/stal-ix/pkgsrc/b
    oras repo tags ghcr.io/stal-ix/pkgsrc/c
    oras repo tags ghcr.io/stal-ix/pkgsrc/d
    oras repo tags ghcr.io/stal-ix/pkgsrc/e
    oras repo tags ghcr.io/stal-ix/pkgsrc/f
) | sort | uniq | grep -v '^$' > _

mv _ 2

diff 2 1 | grep '^+' | grep -v ' ' | tr -d '+' | while read l; do
    rm -rf tmp
    mkdir tmp
    cd tmp
    minio-client get minio/cas/${l} ${l}
    oras push \
        -u pg83 \
        -p ${GHCR_TOKEN} \
        -a "org.opencontainers.image.source=https://github.com/stal-ix/pkgsrc" \
        ghcr.io/stal-ix/pkgsrc/$(echo ${l} | cut -c1-2):${l} ${l}
    cd ..
    rm -rf tmp
done
