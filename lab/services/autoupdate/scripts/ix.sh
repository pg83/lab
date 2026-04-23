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
# gpull exits 7 when there are no new commits — set -e short-circuits
# the rest of this cycle, runit restarts us, next sleep+gpull. Only
# spend time on mut when there's actually something new upstream.
gpull https://github.com/pg83/lab ix
ix mut system
ix mut \$(ix list)
# /bin/runpy is the base64-encoded copy of cg.py installed into the
# realm; its sha256 is a deterministic fingerprint of the deployed
# revision. Log it so Loki carries the current version across the
# cluster — tooling can answer "is this host running the latest
# commit?" without SSH'ing in.
echo "autoupdate_ix: deployed runpy-sha256=\$(sha256sum /bin/runpy | awk '{print \$1}')"
EOF

chmod +x ${out}/bin/*
{% endblock %}
