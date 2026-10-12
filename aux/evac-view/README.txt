Evacuation view: https://reklama.homelab.cam

Covers shards 0..499, including the completed initial batch 200..249.

EvacViewData (root, lab1) reads the controller status and the existing
receiver checkpoint/receipt files. It discovers the supervised evacuation
SSH daemon's mount namespace through /proc/PID/root, so it works after a
reboot without relying on the initial manual /srv/evac mounts. No archive
contents are read. A bounded, read-only SSH probe every 30 seconds reads
source staging disk usage and download marker names using the controller's
existing dedicated identity. The transfer scripts and their services are
not changed or restarted by this monitor.

Only whitelisted status fields are atomically published every five seconds
to /var/run/evac_view_data/public/status.json. Raw logs, SSH keys, tokens,
source paths and the controller plan are not served.

EvacView runs as the separate unprivileged evac_view user on lab1's gofra
address, port 8102. It serves exactly /, /app.js, /style.css and /api/status;
there are no write operations, archive downloads or directory listings.
All replicas of the existing Cloudflare tunnel route reklama.homelab.cam
to this backend. The mesh proxy also exposes reklama.lab1.mesh.
The DNS record is a proxied CNAME to the existing shared tunnel:
  4b335fae-9cd1-40bb-9868-08deb4a23cb7.cfargotunnel.com

Progress is by completed shards, not an estimate of compressed total size.
Received bytes include only durable checkpoint bytes or final receipt bytes;
a completed archive also needs to exist at the receipt's exact size. This
does not add a full on-disk checksum reread. Current throughput is calculated
from about 40 seconds of durable byte growth, with a 15-minute in-memory
history. Initial sampling, missing volumes and counter resets invalidate the
rate instead of inventing a spike. Controller and browser staleness are shown.

Deploy through normal lab git commit/push/autoupdate. Both servants are
supervised and start again after reboot; the graph starts a new history.

Verification:
  python3 aux/evac-view/test_view.py
  python3 tst/dryrun.py
  python3 tst/test_class_hash.py
  python3 tst/test.py | diff tst/canon.json -
