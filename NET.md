# gorn endpoint IP concentration (CI/dispatch ingress)

Observed 2026-04-24 after investigating a nebula packet-drop burst
(lab1 udp_0_drops peaked at 194/s, 217k drops over 1h). Not a nebula
bug — the underlay NICs show the same story: one NIC saturated,
siblings idle.

## Symptom

Snapshot of physical-NIC bandwidth, steady-state CI load:

| host | RX hot NIC         | RX siblings (Mbit/s)   |
|------|--------------------|------------------------|
| lab1 | **eth0 146 Mbit/s** | eth1 4, eth2 2, eth3 16 |
| lab2 | **eth0 100 Mbit/s** | eth1 3, eth2 2, eth3 2 |
| lab3 | **eth1 163 Mbit/s** | eth0 4, eth2 0.2, eth3 0.4 |
|      | **eth1 TX 235 Mbit/s** (reply path) |          |

TX spreads across eth1/2/3 because egress source selection is
per-flow — the kernel picks whichever NIC the route table says
reaches the destination. RX does not spread: a packet destined for
`192.168.100.16` physically arrives on whichever NIC owns that IP,
and that's a single NIC per host.

## Cause

Every gorn endpoint is registered with **one** destination IP:

```
$ curl -s http://lab1.nebula:8027/v1/endpoints | jq '[.endpoints[].host] | group_by(.) | map({ip:.[0], n:length})'
[ {ip:"192.168.100.16", n:22},
  {ip:"192.168.100.17", n:20},
  {ip:"192.168.100.18", n:14} ]
```

22 lab1 workers, all behind `100.16`. That IP lives on exactly one
physical NIC per host (eth0 on lab1/lab2, eth1 on lab3 — the
layout is asymmetric). All CI/molot SSH dispatch, stdin upload,
stdout download traffic lands on that single NIC. The other three
NICs per host do nothing on RX.

Headline: we're running at **1/4 of the theoretical ingress
capacity** for worker traffic, and a burst fills one NIC's rmem /
nebula SO_RCVBUF while the rest are idle.

## Options

### A. Spread endpoints across NICs (recommended)

In `cg.py` `GornSsh.gorn_endpoints()`, rotate the endpoint `host`
over the host's NIC IPs instead of pinning to one. For lab1's 22
endpoints on 4 NICs: 6/6/5/5 per NIC (round-robin by index).

Ignite/molot pick an endpoint at random from the full list, so the
spread is automatic — no client changes. `ip route` already knows
how to reach each IP on its own NIC; nothing else moves.

**Pros.**
- Pure cg.py change, one loop. No kernel, no routing, no patches.
- Symmetrical with the MinIO (A) remedy above: MinIO pins *egress*
  per uid, this pins *ingress* per endpoint.
- Works for both nebula-tunnel traffic (if the registered IP is a
  `.nebula` host, we'd pick per-NIC nebula IPs) and physical IPs.

**Cons.**
- Endpoint count stays the same, so per-NIC worker density drops
  from 22 to ~5. If a single NIC's kernel-side rmem / nebula queue
  is the bottleneck, that's a 4× headroom win; if the bottleneck
  is a single shared nebula reader goroutine, it doesn't help.
  (Current data suggests the former — drops correlate with NIC RX
  peaks, not CPU.)
- Asymmetric NIC layout (lab3 hot NIC is eth1, not eth0) means
  the rotation table has to be per-host, not a universal list.

### B. Single virtual IP + ECMP

Register endpoints at one logical IP that lives on all four NICs
via ECMP. Theoretically clean, practically: needs working L3 ECMP
on the switch, same-subnet quirks, and `ip rule`/`ip route`
plumbing on every host. Too much machinery for a 3-host homelab.

### C. DNS round-robin

Register endpoints as `labN.local` with 4 A records. SSH picks
one per connection; NIC usage averages out. But SSH connection
reuse (ControlMaster in gorn's SSH) pins to first-resolved IP for
the session, so reuse clashes with rotation. Also leaves
measurement gaps — we'd no longer see per-endpoint which NIC it
hits.

## Recommendation

**Go with (A).** One `cg.py` loop producing per-NIC endpoint
rotations. Measure before/after on `node_network_receive_bytes_total`
by NIC to confirm the 146 Mbit/s lab1 eth0 peak spreads to ~36
Mbit/s × 4 NICs.

## Open questions

- Do we register by `192.168.100.X` (physical eth0/eth1 /24) or
  by `labN.ethK` name? Names are stabler across reconfig but add
  a DNS step to every dial; IPs skip DNS but pin to numbers that
  may move.
- Nebula endpoints are also concentrated (`labN.nebula` is a
  single IP per host inside the overlay). Same rotation story
  applies; worth doing in the same pass since that's where the
  194/s drop burst originally showed up.
- Does molot need the same rotation for its own dispatch
  (IX build-graph → gorn task fan-out)? If molot goes through
  gorn/ignite, it rides the same endpoint list; no extra work.

---

# etcd leader churn during autoupdate deploys (2026-04-24)

Follow-up to the nebula-drops investigation. After confirming that
nebula drops weren't the dominant driver of leader elections, the
real signal turned out to be **etcd wal_fsync p99 crossing the
1s raft election-timeout during autoupdate deploy bursts**.

## Evidence

xcorr over 6h, etcd_private leader changes vs candidates:

| signal                                  | max r | lag    |
|-----------------------------------------|------:|:-------|
| `fsync ← sdd write_latency (same host)` | +0.826 | 0s    |
| `fsync ← sdd write_bytes/s (same host)` | +0.822 | 0s    |
| `fsync ← sdd util% (same host)`         | +0.680 | 0s    |
| nebula udp drops                        | +0.13 | noise  |

Event-study against autoupdate deploy timestamps (20 events/host, 6h):

| metric            | deploy peak / baseline |
|-------------------|:----------------------:|
| wal_fsync p99     | **2.49×** (0.86s → 2.13s) |
| sdd write_bytes/s | 2.01× |
| sdd io_time %     | 1.41× |
| **leader changes** | **2.22×** |
| proposals/s       | 0.57× (↓ — services mid-restart) |

## Why it isn't a disk-hardware problem

sdd is a 256 GB SATA SSD over a Silicon Motion USB-SATA bridge
(`0x090c:0x1000`). `disk_await` (`bin/dev/scripts/disk_await.py`)
shows steady-state `w_await` of 1–2 ms at 10–50 IOPS, `util` 2–8 %.
Hardware is fine. The 2.1 s fsync p99 tail is almost certainly
**ext4 journal contention** — `ix mut` writes many files during
deploy, journal commits queue, `fsync(wal_fd)` waits for the
whole queue to flush.

SMART isn't proxied through this bridge (`-d sat`, `-d sntasmedia`,
`-d sntjmicron` all return "unsupported"). We don't have lifetime
TBW visibility, but the live latency numbers are the ones that
actually matter for etcd correctness.

## Chosen fix: raise raft timeouts

Instead of fighting the disk, tell raft that 2 s fsync spikes are
acceptable. Bump both members' timings 10× above defaults:

- `--heartbeat-interval=1000ms` (was 100 ms default)
- `--election-timeout=10000ms`   (was 1000 ms default)

The 10× ratio between election-timeout and heartbeat-interval is
etcd's own recommendation and is preserved.

### Trade-offs

- Legitimate leader crashes take up to 10 s to detect instead of 1 s.
  For the homelab, callers (gorn, loki, molot) retry happily on the
  `leader changed` path, so this is invisible.
- Once an election does fire, it takes ≥ one election-timeout, so
  real downtime windows grow from ~1 s to ~10 s. Rare event.
- No durability impact. Same fsyncs, same WAL, same data path.

### Procedure

Rolling restart, one member at a time:

1. Bump `--heartbeat-interval` + `--election-timeout` flags in
   `EtcdPrivate.run()` and `EtcdSecondary.run()` in `cg.py`.
2. Commit → autoupdate rolls out.
3. Because autoupdate restarts services sequentially across hosts,
   the natural cadence is already rolling. Just watch
   `etcd_server_leader_changes_seen_total` during the rollout to
   confirm the cluster stays up.
4. Don't force all three to reload inside the same 10 s window
   — if autoupdate lands on all hosts within that, pause one host's
   service manually and unblock after the others settle.

## Other options considered, not taken

- **WAL on tmpfs** — eliminates fsync on sdd, but on the user's
  reality of "several full power-offs per year", losing WAL on all
  3 nodes simultaneously means etcd won't start and needs manual
  `--force-new-cluster` recovery. Rejected: too much operator burden
  for rare-but-real events.
- **`data=writeback` on rootfs ext4** — would remove journal
  ordering of data writes and cut the fsync tail. Viable, but
  quieter durability behavior on crash. Parked.
- **ionice / cgroup `io.weight` for etcd** — pushes etcd above ix
  mut in the IO queue. Smaller effect than raising timeouts, but
  composable. Worth doing later if timeout bump isn't enough.
- **Replace the USB-SATA bridge with native SATA** — would help
  if bridge were the problem; `disk_await` showed it isn't.
- **`ix mut` no-op symlink skip** — would reduce deploy-time writes
  overall. Deep ix change, deferred.

## Status

Deferred to 2026-04-25 — TO DO:

1. Edit `EtcdPrivate.run()` / `EtcdSecondary.run()` in `lab/cg.py`
   to inject `--heartbeat-interval=1000 --election-timeout=10000`.
2. Re-canonize `tst/canon.json`.
3. Commit, let autoupdate roll. Watch
   `changes(etcd_server_leader_changes_seen_total[5m])` drop to
   ~zero outside real failure.
