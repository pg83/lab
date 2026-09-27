{% extends '//die/hub.sh' %}

{# repology jobs: upstream code from the ogorod mirror at run time, ours
   is the driver, the shims and the curl transport in scripts. #}

{% block run_deps %}
bin/tar
bin/xz
bin/curl
bin/zstd
bin/gzip
bin/bzip2
bin/brotli
bin/python
bin/git/unwrap
bin/minio/patched/client
bin/repology/scripts
{% endblock %}
