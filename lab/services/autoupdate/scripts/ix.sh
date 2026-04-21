{% extends '//die/gen.sh' %}

{% block install %}
mkdir -p ${out}/bin

cat << EOF > ${out}/bin/ix
#!/usr/bin/env sh
exec /var/run/autoupdate_ix/ix/ix "\${@}"
EOF

cat << EOF > ${out}/bin/autoupdate_cycle
#!/usr/bin/env sh
set -xue
sleep 10
gpull https://github.com/pg83/lab ix
ix mut system
ix mut \$(ix list)
# /bin/runpy is the base64-encoded copy of cg.py installed into the
# realm; its sha256 is a deterministic fingerprint of the deployed
# revision. Log it so Loki carries the current version across the
# cluster — tooling can answer "is this host running the latest
# commit?" without SSH'ing in.
echo "autoupdate_ix: deployed runpy-sha256=\$(sha256sum /bin/runpy | awk '{print \$1}')"
timeout 60s etcdctl watch --prefix /git/logs/git_lab | gnugrep --line-buffered 'PUT' | head -n 1
EOF

chmod +x ${out}/bin/*
{% endblock %}
