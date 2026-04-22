# FS.md — object-storage / distributed FS notes

Research done 2026-04-22 after the MinIO bitrot incident on lab3 (XFS
metadata corruption on `/dev/sdc` → silent bad EC shards → reads
hanging in reconstruct loops). This file is the scratchpad for "what
would we switch to, if we did."

Current setup: 3 hosts × 3 HDDs (~3.6T each) + USB-boot SSD. XFS on
data disks. 32 GB RAM / host. MinIO distributed, 3 instances per host,
EC across 9 drives. Buckets: `gorn`, `loki`, `samogon`, `geesefs`.

## TL;DR ranked shortlist

1. **Garage v2.3.0** — Rust, AGPL-3. One process per host, replication-only
   (1/2/3x), designed for this exact scale. No EC → no reconstruct-hang. Per-block
   BLAKE2 + background repair worker. Trade-off: 3x replication on 32 TB raw ≈
   10 TB usable (vs ~20 TB under MinIO EC).
2. **SeaweedFS 4.21** — Go, Apache-2. Hybrid replication (hot) + EC (warm sealed
   volumes). ~2-4 week release cadence, very active. Closest drop-in to MinIO
   in layout. Filer metadata needs external store (sync-SQLite or Postgres).
3. **Ceph Squid 19.2.x (RadosGW)** — C++, LGPL. Best-in-class bitrot
   (BlueStore per-object CRC32C + scheduled deep-scrub with auto-heal), best S3
   compatibility. Cost: 32 GB RAM is tight (9 OSDs × ~1.5 GB + mon/mgr/rgw) and
   the operational load is a step up. Only if we commit to part-time Ceph ops.

## MinIO status (why we're even looking)

- 2025-05 — admin console removed from Community edition [PR #3509]
- 2025-10 — binary and Docker distributions halted
- 2026-02-12 — repo formally in "maintenance mode"
- OpenMaxIO fork revived the console but is a bridge, not a destination. Still
  AGPL-3. No commitment to long-term upstream.

Sources:
- https://blocksandfiles.com/2025/06/19/minio-removes-management-features-from-basic-community-edition-object-storage-code/
- https://www.infoq.com/news/2025/12/minio-s3-api-alternatives/
- https://blog.vonng.com/en/db/minio-resurrect/

## Candidate detail

### Garage (Deuxfleurs)

- Latest: v2.3.0 (2026-04-16), v1.3.1 LTS (2026-01-24). Actively developed.
- Design explicitly targets 3–10-node self-hosted clusters.
- Replication only (no EC, and they will not add it — documented decision).
- Per-block BLAKE2 checksums, background repair worker.
- S3 API good for our clients; Garage+Loki is a documented combo.
- Memory: tens-of-MB per node idle, one process per host.
- Gotchas: no object-lock/WORM. Some legacy XML quirks were fixed only in the
  v2.2.0 → v2.3.0 window (see changelog).
- 3-host fit: **ideal**.

Links:
- https://git.deuxfleurs.fr/Deuxfleurs/garage/releases/tag/v2.3.0
- https://garagehq.deuxfleurs.fr/documentation/design/goals/

### SeaweedFS

- Latest: 4.21 (2026-04-19). Very high release cadence.
- Volume-server + filer + optional S3 gateway.
- EC: 10+4 Reed-Solomon on sealed (30 GB default) volumes. Hot data uses
  replication; warm data EC'd — we'd get MinIO-style space efficiency for
  `gorn`/`samogon`, without EC pain on live writes into `loki`.
- Bitrot: per-needle CRC, self-healing replication rebalance. Scrub lighter
  than Ceph; sometimes `volume.fix` has to be triggered manually.
- Memory: 200-500 MB per volume-server typical.
- Filer metadata is the failure domain — put it on a Raft-replicated store
  (built-in leveldb/sqlite3 synced per node, or external Postgres).
- S3 API: broad, not 100%. Loki, aws-sdk-go-v2, restic, rclone all work.
  Occasional multipart-copy quirks.
- "Enterprise" fork is a growing concern — paywalled EC improvements — but
  base OSS version is still maintained by chrislusf directly.

Links:
- https://github.com/seaweedfs/seaweedfs/releases/tag/4.21
- https://github.com/seaweedfs/seaweedfs/discussions/6566 (HDD EC tuning)

### Ceph Squid (RadosGW)

- 19.2.3 released 2025-09. Reef EOL 2026-03-31. Tentacle (20.x) next.
- BlueStore stores per-object CRC32C, verifies on every read, weekly deep-scrub
  recomputes + compares across replicas/EC shards. Alerts built-in.
- RGW S3 is the most complete non-AWS implementation.
- 3-node Ceph is supported but painful: mon+mgr+OSD+RGW per host. 32 GB RAM
  is tight but feasible if we're careful with per-OSD memory caps.

Links:
- https://ceph.io/en/news/blog/2025/v19-2-3-squid-released/
- https://docs.ceph.com/en/squid/rados/operations/erasure-code/

### RustFS — skip for now

- Still at 1.0.0-alpha.98 as of 2026-04-22. Docs say "do NOT use in production."
- Positioned as MinIO-in-Rust drop-in. Chinese-led project, claims 2.3x perf
  on 4KB objects. Revisit in 6-12 months.
- https://github.com/rustfs/rustfs/releases/tag/1.0.0-alpha.98

### Dead / irrelevant

- **Zenko CloudServer** — Node.js single-node S3 gateway, not a distributed
  store. Wrong shape.
- **OpenIO** — dead since OVHcloud absorbed in 2020.
- **OpenStack Swift** — irrelevant outside full OpenStack.
- **GlusterFS** — Red Hat ended 2024-12-31, 11.2 is life-support, see
  https://github.com/gluster/glusterfs/issues/4298
- **LizardFS** — dormant. MooseFS is the living fork.
- **MooseFS 4.58.4 (2026-03-19)** — EC is Pro-only. CE is replication + single
  master (hot-standby metalogger is the classic weak point).
- **BeeGFS** — HPC-focused, wrong shape for CI/log/torrent mixed workloads.

### Non-S3 / FS-level alternatives

- **CephFS / RBD** — same deployment cost as RadosGW, same bitrot strength.
  Only worth it if we need POSIX semantics.
- **JuiceFS v1.3.1** (2025-12-02) — FS-on-object-store. Still needs an object
  store underneath plus an external metadata DB (Redis/Postgres/TiKV). Adds a
  layer, doesn't remove one. Worth it only if the actual need is POSIX.
- **DRBD + single-node NFS** — honest option if we ever decide "distributed
  was the mistake." Decades of XFS+DRBD production hardening. Loses horizontal
  read scaling, but we don't need it at 9 drives.

## Bitrot / data integrity — the real lesson from the incident

The failure mode: XFS metadata corruption on lab3 sdc (eventually repaired via
`xfs_repair`) silently produced bad EC shards. MinIO only caught it on read
(`file is corrupted (cmd.StorageErr)`), tried reconstruct, and reads hung.

Three paths out, not mutually exclusive:

1. **Move to ZFS under the object store.** End-to-end per-block checksums,
   periodic `zpool scrub`, corruption is caught and corrected below the app
   layer. Works under MinIO/Garage/SeaweedFS. With 32 GB RAM cap ARC at 4-8 GB.
2. **Pick a store with built-in periodic deep-scrub.** Ceph is the gold
   standard. Garage's repair worker walks blocks. SeaweedFS has `volume.fix`.
   MinIO's `mc admin heal` is read-time + manual — which is exactly why we got
   bitten.
3. **Both** — belt and suspenders. ZFS per drive + app-level replication/EC +
   scheduled app scrub. Monthly ZFS scrub + weekly app scrub is realistic on
   these HDDs.

Self-heal, automatic vs on-demand:
- Ceph: automatic (deep-scrub schedule) ✓
- Garage: automatic (repair worker) ✓
- SeaweedFS: semi-automatic (worker loop) ⚠️
- MinIO: read-time + manual heal only ✗

## Client compat notes (drop-in S3 for our stack)

- **loki** — MinIO, Ceph RGW, SeaweedFS, Garage, AWS S3 all work. Garage+loki
  is a documented combo.
- **aws-sdk-go-v2 (gorn, samogon)** — works with all. Edge cases around
  checksum mode (SHA-256 trailer), virtual-host vs path-style, presigned POST.
  Garage fixed several of these between v2.2.0 and v2.3.0.
- **logcli** — standard S3, no surprises.
- **rclone / restic** — all fine with Garage, SeaweedFS, Ceph RGW. SeaweedFS
  has occasional surprises with multipart copy.

## If we actually migrate

Recommendation given our constraints:

- **Simplicity > space efficiency** → Garage v2.3.0 on ZFS-per-drive,
  replication=3. Lowest operational cost. Structurally eliminates our
  EC-reconstruct-hang. ~10 TB usable.
- **Need full ~20 TB usable** → SeaweedFS 4.21 on ZFS-per-drive, EC for
  warm buckets (gorn, samogon), replication for hot (loki). Filer metadata on
  Postgres or synced SQLite.
- **Ceph** only if we're committing a person-fraction of ops time.

## TODO (not migrating today, but worth queuing)

- Schedule ZFS experiment on one lab3 disk once sdb is replaced — benchmark
  fsync + scrub behavior vs XFS on the same hardware.
- When/if migrating, plan is per-bucket cutover, not big-bang. Loki is the
  easiest (schema rotates anyway); gorn artifacts are next (immutable); samogon
  pieces last (read-heavy from SFTP, downtime sensitive).
- Revisit RustFS in ~6 months once it leaves alpha.
