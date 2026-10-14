Completed Plutonium evacuation, shards 0..499

Retired on 2026-10-14 after all 500 shards arrived successfully:
11,317,817,449,517 compressed bytes. The evac_transfer, evac_ssh,
evac_view_data and evac_view servants and the dashboard ingress were removed
from the cluster configuration. The source worker/reverse services and local
reminder are disabled. The four target XFS partitions are unmounted.
Archives and receipts remain under incoming-pg/banners_remote on those disks;
the filesystem UUIDs and readback paths are in ../evac-ssh/README.txt.
UID 2027 remains reserved for the archived files' pg ownership.
Controller state and verification reports remain in /srv/evac-transfer on lab1.
The random samples 329 and 475 were fully decompressed and extracted into RAM;
both archive SHA-256 hashes matched their receipts, zstd/tar exited 0, and each
extraction contained 1,767 files. The temporary extracted copies were removed.
Report: /srv/evac-transfer/verification-20261014T223153Z/report.json.
The documentation below describes the historical deployment.

Source: merlin.klg.yp-c.yandex.net, account pg.
Installed script: ~/down2.py (copy of transfer.py managed by lab1).
~/down2.sh delegates to it; old script is ~/down2.sh.sandbox-original.
Snapshot IDs are pinned by ~/pluto.txt. YT is read only by this pipeline.

Two source downloader threads take shards from one shared queue alongside up
to four archive uploaders. At most six snapshots occupy staging: uploads plus
two preparations/downloads ahead. Each thread estimates required space and
reserves its estimate under a shared lock, leaving at least 20 GiB free.
Both monitor free space during download and stop before exhausting it.
Incomplete downloads have an ownership marker; on retry only those downloads
can be discarded and downloaded again. Unmarked existing directories are refused.
Upstream stat/download command failures retry the same pinned snapshot with a
30-second backoff, doubling up to five minutes. Each thread retries its own shard;
the other thread continues preparing subsequent shards. Both threads can wait
if both current shards fail. Prepared archive uploads keep running during these
retries; an upstream failure never restarts them. Per-shard *.retry.json state
is reported by the controller and shown as warnings in the delivery view.
Identity, integrity and explicit local storage checks remain fatal.

GNU tar preserves hardlinks and is generated as a stream. No intermediate
tar or compressed archive is written on merlin. Zstd level 4 with two
compression threads per archive is enabled by default.
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
    banners_remote-<N>--<snapshot>.tar.zst.partial       unfinished archive
    banners_remote-<N>--<snapshot>.tar.zst.transfer.json durable checkpoint
    banners_remote-<N>--<snapshot>.tar.zst               finished archive
    banners_remote-<N>--<snapshot>.tar.zst.json          size, SHA-256, identity
Shard 200 from the initial trial remains a .tar.lz4 archive.

The paths above are visible inside the evacuation SSH service (port 8101).
Existing host mounts expose the same data at:
  /srv/evac/<volume>/incoming-pg/banners_remote/
Those host mounts were created during setup. After boot, the supervised SSH
service mounts each filesystem by UUID in its own namespace, so port 8101
is the stable way to inspect the archive directories.

Final rename happens only after tar and the compressor exit successfully and both ends agree
on total bytes, chunks and SHA-256. A receiver failure leaves a partial file.
Resume verifies the durable prefix, truncates any uncommitted tail and
regenerates the same stream from the immutable downloaded snapshot, discarding
the already received prefix. Compression and Zstd level are pinned in each shard's placement:
changing the plan affects only new shards. Old completed or partial archives
keep their existing format and level. Legacy Zstd records without zstd_level
mean level 1; new placements use --zstd-level (default 4). The receiver records
the level in checkpoints and receipts and refuses a mismatch on resume.
Changing chunk size while resuming is refused.
A completed archive is never silently overwritten.

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
  /srv/evac-transfer/plan.json       enabled, start/end, uploads, lanes, compression, zstd_level, chunk_mib
  /srv/evac-transfer/status.json     last contact, systemd state, completed shards
  /srv/evac-transfer/source-id       dedicated SSH identity, never committed
  /srv/evac-transfer/source-known_hosts

Bootstrap plan: enabled, range 200..249, four archives, eight lanes each, Zstd,
remove verified source staging. The active plan was expanded to 0..499 after
the initial 200..249 completed. Existing completion records skip downloading;
the receiver confirms the saved archive receipt without retransmitting it.
Change plan.json atomically to adjust the range (within 0..499) or concurrency.
zstd_level (1..19, default 4) applies only to shards without saved placements.
Setting enabled=false gracefully stops and disables the
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

--compression none writes a plain tar; --compression lz4 uses LZ4 -1.
The selection applies to new shards. Existing shards retain their saved format.
Zstd is available on merlin as /usr/bin/zstd; --zstd can override the executable.

LZ4 on merlin is extracted from the Ubuntu lz4 package in the user's cache:
  ~/.cache/evac-tools/lz4/root/usr/bin/lz4
--lz4 can specify another executable. No system package installation is needed.

Read an archive later:
  zstd -dc banners_remote-201--<snapshot>.tar.zst | tar -tf -
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
unnecessary source worker restart, mixed compression across shards, and
regeneration/resume of the compressed Zstd stream followed by decompression.
Level migration tests cover legacy -1 checkpoints, -4 checkpoints, rejection
of level changes on an existing archive, and keeping saved levels across plan changes.

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

Zstd comparison on the same shard (tar size unchanged):
  zstd -1 -T2: 23,243,383,635 bytes (21.65 GiB); 15.26% saved; ratio 1.1801.
  Time: 78.53 s, 333.13 MiB/s of tar input; child CPU time: 139.05 s.
  5.72% smaller than the LZ4 archive. LZ4 used one compression thread;
  Zstd used two. Both are faster than the 1 Gbit/s network path.
  Compressed stream SHA-256:
    8be5aaea55213eaac8a6ad79cc5c081fe0f593dbff5f6e2a477e51fe88e6addc

Level selection on 2026-10-12 (zstd 1.4.8, two threads):
  Same 4 GiB sample: eight evenly spaced 512 MiB ranges of shard 4's tar.
  -1: 3,617,780,355 bytes, 15.767% saved, 611.53 MiB/s input.
  -4: 3,514,143,830 bytes, 18.180% saved, 281.37 MiB/s input.
  -5: 3,501,032,373 bytes, 18.485% saved, 127.19 MiB/s input.
  Level 4 produces 2.865% fewer bytes than level 1 on this sample;
  level 5 saves only another 0.373% while more than doubling compression time.
  These are sampled compression measurements alongside the live transfer,
  not end-to-end transfer rates. The new default is 4; saved levels stay pinned.
