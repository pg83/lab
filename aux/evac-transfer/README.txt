Plutonium evacuation, shards 200..249

Source: merlin.klg.yp-c.yandex.net, account pg.
Installed script: ~/down2.py (copy of transfer.py managed by lab1).
~/down2.sh delegates to it; old script is ~/down2.sh.sandbox-original.
Snapshot IDs are pinned by ~/pluto.txt. YT is read only by this pipeline.

One source downloader runs alongside up to four archive uploaders. At most
five active snapshots occupy staging: current uploads and one download ahead.
The downloader estimates required space and leaves at least 20 GiB free.
It also monitors free space during download and stops before exhausting it.
Incomplete downloads have an ownership marker; on retry only those downloads
can be discarded and downloaded again. Unmarked existing directories are refused.

GNU tar preserves hardlinks and is generated as a stream. No intermediate
tar or tar.lz4 file is written on merlin. LZ4 level 1 is enabled by default.
Chunks are 64 MiB, with eight SSH transfers in flight per archive and two
concurrent initial handshakes across all archives. Compression, network
transfer and target writing overlap. --uploads (1..4) controls concurrent
archives and --lanes controls each archive's SSH streams.
Each source chunk stays available in RAM until acknowledged; a failed chunk
is retried up to three times. Four archives use around 2 GiB of receiver RAM.

The SSH helper on lab1 is deployed by the aux/evac-transfer package:
  /bin/evac-transfer
It is invoked within the existing evacuation SSH account. SSH host keys are pinned.
Source identity: ~/qw; destination: pg@[64:ff9b::5bc:67fb]:8101.

Chunks arrive into a private /dev/shm directory. A single writer reads them
in archive order and appends to one HDD file. Each chunk is checked with
SHA-256, fsynced, and checkpointed before acknowledgement. Out-of-order arrival
does not cause out-of-order HDD writes. The RAM copy is then removed.

The idle target volume with most free space is selected once per snapshot;
its placement is recorded for resume. Four independent targets are available:
  seagate-a, seagate-b, hgst-a, hgst-b
Each target receives at most one archive at a time. By the operator's request,
seagate-a and seagate-b are scheduled independently even though they share a disk.

Destination layout:
  /home/pg/<volume>/banners_remote/
    banners_remote-<N>--<snapshot>.tar.lz4.partial     unfinished archive
    banners_remote-<N>--<snapshot>.tar.lz4.transfer.json  durable checkpoint
    banners_remote-<N>--<snapshot>.tar.lz4             finished archive
    banners_remote-<N>--<snapshot>.tar.lz4.json        size, SHA-256, identity

The paths above are visible inside the evacuation SSH service (port 8101).
Existing host mounts expose the same data at:
  /srv/evac/<volume>/incoming-pg/banners_remote/
Those host mounts were created during setup. After boot, the supervised SSH
service mounts each filesystem by UUID in its own namespace, so port 8101
is the stable way to inspect the archive directories.

Final rename happens only after tar/lz4 exit successfully and both ends agree
on total bytes, chunks and SHA-256. A receiver failure leaves a partial file.
Resume verifies the durable prefix, truncates any uncommitted tail and
regenerates the same stream from the immutable downloaded snapshot, discarding
the already received prefix. Changing compression or chunk size while resuming
is refused. A completed archive is never silently overwritten.

After confirmed completion, source staging is removed unless --keep-source
was specified (which retains completed snapshots too). Remote archive receipts remain available. No source YT data is
deleted. Download logs and state live in ~/.cache/evac-transfer/pipeline/.

Durable service

EvacTransfer in lab/cg.py registers the evac_transfer servant on lab1.
Deployment is the standard git commit/push/autoupdate path. It reconciles
merlin's systemd user service every 20 seconds; data transfer belongs to
systemd, never to a controlling SSH session. A controller restart reconnects
without restarting an unchanged worker. A changed plan or script updates the
worker, which resumes durable archive checkpoints. Source worker failures
restart automatically after 30 seconds. Successful completion stays in
active/exited systemd status rather than rerunning the range.

Persistent state on lab1 (root only):
  /srv/evac-transfer/plan.json       enabled, start/end, uploads, lanes, chunk_mib
  /srv/evac-transfer/status.json     last contact, systemd state, completed shards
  /srv/evac-transfer/source-id       dedicated SSH identity, never committed
  /srv/evac-transfer/source-known_hosts

Default plan: enabled, range 200..249, four archives, eight lanes each, LZ4,
remove verified source staging. Change plan.json atomically to adjust the
range or concurrency. Setting enabled=false gracefully stops and disables the
source worker; the controller and reverse connection remain available.

Progress:
  # on lab1
  tail -f /var/run/evac_transfer/std/current
  cat /srv/evac-transfer/status.json
  # on merlin
  systemctl --user status evac-transfer.service evac-reverse.service
  tail -f ~/.cache/evac-transfer/pipeline/service.log

The reverse SSH connection has its own enabled systemd user unit on merlin,
evac-reverse.service (included here). loginctl enable-linger pg makes both
services start at boot and survive logout. It reconnects after five seconds;
SSH keepalives detect dead connections. No laptop/VPN is needed for this path.
Unit bootstrap: copy evac-reverse.service to ~/.config/systemd/user/, run
sudo loginctl enable-linger pg, systemctl --user daemon-reload, then
systemctl --user enable --now evac-reverse.service. The existing key ~/qw and
pinned lab1 host key must already be present. There must be only one reverse
connection listening on lab1 port 18122.

Manual trial (disable the managed worker in plan.json first):
  ./down2.sh --start 200 --end 200 --uploads 1 --keep-source \
    --remote-helper /bin/evac-transfer
The source pipeline has a file lock, so two runners cannot manage it at once.

--compression none writes a plain tar. Select the format before starting a
new transfer; receipts and checkpoints are tied to that format.

LZ4 on merlin is extracted from the Ubuntu lz4 package in the user's cache:
  ~/.cache/evac-tools/lz4/root/usr/bin/lz4
--lz4 can specify another executable. No system package installation is needed.

Read an archive later:
  lz4 -dc banners_remote-200--<snapshot>.tar.lz4 | tar -tf -

Control access from home.mesh:
  ssh -F /home/pg/.cache/evac-access/ssh_config merlin-evac
This uses the existing reverse SSH on lab1 loopback 18122, independently of VPN.

Local verification:
  python3 lab/aux/evac-transfer/test_transfer.py
Tests cover out-of-order chunks, corrupt incoming data, durable-prefix
corruption, truncation of uncommitted data after interruption, already
completed archives, and sender resume with hardlinks preserved in tar.
They also verify concurrent archives on all four targets, bounded prefetch,
saved placement after restart, and controller reconciliation without an
unnecessary source worker restart.

Measured shard 200, snapshot 20261011T151038Z_603251:
  Native Plutonium download: 25.5 GiB in 29.28 s.
  Deterministic tar: 27,429,744,640 bytes (hardlink payload stored once).
  LZ4 -1: 24,654,806,227 bytes; 10.12% saved; ratio 1.1126.
  Compression benchmark: 129.99 s, 201.23 MiB/s of tar input.
  Compressed stream SHA-256:
    b758167228abeefd658a5762ea87f658ffd3ae676cb540b9655a56b16ee67317
  Trial archive committed on seagate-b with exactly this size and SHA-256.
  A real interruption resumed from 6.5625 GiB; steady transfer after resume
  was about 480 Mbit/s (one archive with 16 lanes).
