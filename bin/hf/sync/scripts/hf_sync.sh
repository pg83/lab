#!/usr/bin/env sh

set -xue

echo ${PATH}

sleep 100

(cd pkgsrc && git pull) || (rm -rf pkgsrc && git clone --filter="blob:none" --depth="1" --no-checkout "https://huggingface.co/datasets/stal-ix/pkgsrc")

cd pkgsrc

rm -f 1 2 _

minio-client ls minio/cas | grep STA | sed -e 's|.* ||' | sort | grep -v '^$' > 1
git ls-tree -r --name-only 'HEAD' | grep 'cas/' | grep -v gitattr | sed -e 's|.*/||' | sort > 2

diff 2 1 | grep '^+' | grep -v ' ' | tr -d '+' | while read l; do
    minio-client get minio/cas/${l} _
    huggingface_cli \
        upload \
        --token ${HF_TOKEN} \
        --repo-type dataset \
        stal-ix/pkgsrc \
        _ cas/$(echo ${l} | cut -c1-2)/${l}
    rm _
done

git pull
