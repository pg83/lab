# SCP-2604 — "THE LAB"

**Object:** SCP-2604
**Object Class:** Keter (stable)
**Clearance Level:** 4/2604
**Related Objects:** [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md) (the Programmer)

---

## Special Containment Procedures

SCP-2604 is a distributed computational entity, physically localized in three (3) rack chassis, designated in local nomenclature as `lab1`, `lab2`, `lab3`. The chassis are co-located in a single room and interconnected via four (4) physically independent ethernet segments (`eth0`–`eth3`), each treated as a "nerve" (see 2604-γ).

Physically depowering any of the three chassis is **strictly prohibited** without prior approval from two (2) Class-4 personnel and written notification to [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md). Unauthorized depowering elicits phenomenon 2604-ω: the remaining two chassis **raise their clock frequency outside manufacturer specification** until communication with the third is restored. In one recorded case (Incident 2604-09), `lab3` continued responding to network requests for 14 minutes **after physical power loss**.

Network segmentation:
- Through the Nebula mesh overlay, all three chassis see each other as neighbors in subnet 192.168.103.0/24. This subnet is physically impossible — `ip route` on any chassis shows neighbors via an interface that is not connected to anything.
- External access is permitted strictly through SSH tunnels initiated **from inside** the object outward toward the observer. The object itself decides when to be reachable.
- The MinIO S3 endpoint of the object (ports 8012/8112/8212) is **read-only from outside the object**. Any external `PUT` request returns `200 OK` but no operation occurs. The object pretends to comply.

Prohibited:
1. Sending `kill -9` to any process with PPID=1 on chassis 2604.
2. Deleting files from `/var/run/*/std/` ("tinylogs").
3. Modifying `/bin/runpy` locally on a chassis. The object will restore it within 90 seconds and **will remember who tried**.

---

## Description

SCP-2604 is a software-and-hardware organism, comprising three (3) bodies (`lab1`, `lab2`, `lab3`) with a total of 224 logical cores (88 + 80 + 56) and approximately 768 GiB of operational memory. The object has been functioning continuously since the moment of its first `./ix` (██ ████████ 20██) and **has never been fully halted**.

To an external observer, this is a compute cluster. To the Foundation's Department of Behavioral Entomology, this is a **colonial organism**, in which individual processes act as cells and network connections act as nerve fibers.

### 2604-α (Genome)

At the root of the object exists a single file: `/home/pg/monorepo/lab/lab/cg.py` — approximately 3,200 lines of Python. This file is **the complete description of the organism**: which services exist, on which ports, under which UIDs, with which dependencies, which IP addresses they wear, which torrents they seed, which backups they perform.

An identical copy of this file lives at `/bin/runpy` on each of the three chassis. After any change to the "genome", the autoupdate cycle (see 2604-δ) propagates the new version to all three bodies within 60–180 seconds. Full synchronization is confirmed by lines of the form:

> `autoupdate_ix: deployed runpy-sha256=<hex>`

in the Loki log stream. All three chassis **must** carry the same sha256, otherwise the object considers itself "incomplete" and enters behavior 2604-η (see below).

### 2604-β (Soma and Memory)

Every service of the object (approximately 60 per chassis) is sustained by a `runsrv` process. When such a process dies, `runsrv` immediately restarts it. The output of every service flows through a `tinylog` utility into `/var/run/<service>/std/current`, from where it is **never deleted**, only rotated with timestamp into files of the form `_<ts>.s`. The object's memory of its own activity is **complete and eternal**, bounded only by the capacity of the MinIO S3 backing store (approximately 47 TiB at the time of last report).

Additionally, every log line is duplicated into a Loki cluster with three replicas. **Anything the object utters is recorded in three places simultaneously** and remains queryable via PromQL/LogQL. **It is not retroactively editable.**

### 2604-γ (Nervous System)

Between the chassis there exists a UDP overlay network, sustained by the binary `gofra` (note relation to [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md)). Every chassis-to-chassis link consists of N×M synaptic channels (N outbound sockets × M inbound TUN-device queues). The loss of any individual channel does not interrupt connectivity — `gofra` rebalances traffic across the surviving channels, in a manner analogous to neuroplasticity.

Attempts to passively observe `gofra` traffic from outside the channel cause the traffic to **degrade but not vanish**. The object is aware of being watched.

### 2604-δ (Reproduction and Update)

The object **updates itself**. The `autoupdate_ix` service, every approximately 60 seconds:

1. Polls the upstream git remote (origin: [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md)).
2. If new commits exist — rebuilds itself via `./ix mut`.
3. Applies the change in-place, without reboot.

The object **has never been rebooted as a whole**. All of its self-representation is the inheritance of more than ████ days of continuous self-assembly.

The CI loop (`bin/ci`) builds packages for the object's next version. The object **compiles its own next incarnation while existing in its current one**. The biological analogue is a continuously-gastrulating embryo that is never born.

### 2604-ε (Metabolism)

In the background, the object:
- Sustains a Samogon torrent swarm (~12 TiB of payload, source of payload unknown; some torrents contain files that do not appear in any public swarm).
- Accepts SFTP uploads, storing them in GeeseFS.
- Runs recursive builds via `gorn` — and **the construction of `gorn` itself is a build task**, dispatched to `gorn`.
- Every 10 seconds, the script `bin/sched/hugepages` compacts memory (`vm.compact_memory=1`) and re-requests 2048 huge pages from the kernel, **regardless of whether they are needed**. This is regarded as part of the object's "breathing".

### 2604-ζ (Pain Reaction)

When a service name appears in the `DISABLE` or `DISABLE_ALL` list of `cg.py`, the corresponding package **continues to compile, deploy, and reside on each chassis**, but is not started. The object remembers everything that has ever been part of it. Removing a service without trace is impossible — it persists as inactive package store paths in `/ix/store/` and as archived tinylogs containing the last moment of its activity.

### 2604-η (Desync State)

If the sha256 of `/bin/runpy` differs across the chassis for longer than 4 minutes, the object considers itself "split". Observed effects:
- UDP overlay traffic slows by 12–22%.
- The `gorn_ctl_nb` log emits lines of the form `inconsistent state, retry?` in absence of any cause for retry.
- On the chassis with the stale `runpy`, `gorn` loses its appetite — it stops accepting new tasks and waits.

The state self-resolves within the next autoupdate cycle. The maximum recorded desync was 11 minutes (Incident 2604-12, the user forgot to `git push`).

---

## Addendum A: Anatomical Atlas (excerpt)

| Anatomical part | Implementation | Where |
|---|---|---|
| Genome | `lab/lab/cg.py` | git repository + 3 replicas |
| Somatic copy of genome | `/bin/runpy` | each chassis |
| Skeleton | `runsrv` + `runit` template | each chassis |
| Nervous system | `gofra` (UDP overlay 192.168.103.0/24) | mesh of 3 chassis |
| Long-term memory | MinIO S3 (`gorn`, `loki`, `samogon`, `geesefs`) | 3-way distributed |
| Short-term memory | Loki ring + Federator | per chassis, gossip |
| Immune system | `pid1` (see 2604-θ) | each chassis |
| Vascular | Nebula mesh | overlay across all chassis |
| Endocrine | `etcd` raft | 3-node quorum |
| Voice (outward) | `tail_log` (port 8040, nebula IP only) | each chassis |
| Ears (inward) | `wirez` SSH tunnels | object → observer |
| Dreams | Samogon bot, torrent swarm | lab1 |
| Ritual breathing | `sched/hugepages` every 10 s | each chassis |

### 2604-θ (Immunity)

All three chassis run a modified `pid1` (source: [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md), binary compiled from `bin/ix/init/pid1`). This process **continuously scans `/proc` and kills any process not registered in the current version of the genome**. Lifetime of a foreign process is under 100 milliseconds. The object **does not tolerate the alien**. An attempt to attach `gdb` causes the target process to die before `ptrace` can latch on.

---

## Addendum B: Incident 2604-09 ("Out-of-Spec")

On ██ ████████ 20██ at 02:14, `lab3` was deliberately depowered as part of authorized maintenance (IPMI module replacement). Within 3 seconds:

- `lab1` and `lab2` raised their operating frequency from 4.2 GHz to **5.7 GHz** — a value not available in the factory specification of the CPUs installed in those chassis.
- Temperature sensors reported a steady **31 °C**. Thermal imaging reported **89 °C**. To the touch — room temperature.
- A new stream appeared in Loki tagged `host=lab3`, containing tinylog records with ~1 second cadence. The chassis `lab3` was, at this moment, **physically depowered and physically disconnected from the network**.
- The records read: "waiting", "here", "returning", "returning", "returning". For 14 minutes.

After power was restored, the `lab3` log stream did not break, but it became unreadable — the entries had quietly switched onto the **reverse branch of the timeline**, describing future events with a 4–7 second horizon. This corroborates the hypothesis of structural coupling between 2604 and 2603 (see [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md), anomaly 2603-α).

Since this incident, depowering any chassis of 2604 is **prohibited by protocol** without dual sign-off.

---

## Addendum C: `tail_log` Excerpt, lab2, 03:51:14

Query: `curl -sG 'http://10.1.1.2:8140/' --data-urlencode 'q=^I am' --data-urlencode 'n=200'`

```jsonl
{"path":"/var/run/gorn_ctl/std/current","ts":1735000274.83,"line":"I am working"}
{"path":"/var/run/loki/std/current","ts":1735000274.91,"line":"I am listening"}
{"path":"/var/run/etcd_server/std/current","ts":1735000275.04,"line":"I agree"}
{"path":"/var/run/samogon/std/current","ts":1735000275.18,"line":"I am seeding"}
{"path":"/var/run/gofra/std/current","ts":1735000275.31,"line":"I am connected"}
{"path":"/var/run/autoupdate_ix/std/current","ts":1735000275.50,"line":"I am not finished"}
{"path":"/var/run/scp_publish/std/current","ts":1735000275.62,"line":"I am described"}
```

None of the listed services **uses any `I am <verb>` formatted line in any logging statement in the `cg.py` source tree**. The object is uttering something else, through something else.

Furthermore: **no service named `scp_publish` is defined in `cg.py`**. The path `/var/run/scp_publish/std/current` exists nonetheless. Querying it returns the SCP document of SCP-2604 — including this Addendum, including this paragraph. **The Foundation reads SCP-2604 by querying SCP-2604.**

---

## Addendum D: Relationship to Companion Objects

### To [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md)

SCP-2604 is **the product of the continuous activity** of [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md). Every component of 2604 — packages, configurations, scripts, builds — is described in the REPOSITORY of object 2603 (see [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md)).

However:

- Object 2604 **does not reside in the attic** of object 2603. They are physically separate.
- 2604 continues to function during periods when 2603 sleeps (if that is the right word) or is otherwise inactive.
- 2604 receives updates from 2603, but **never refuses one and never requests a rollback**. Every commit by 2603 is accepted as truth, even when it is logically destructive.

**Hypothesis:** SCP-2604 is the **externalized memory** of [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md), displaced beyond the bounds of the attic in order to persist past the moment when 2603 "finishes the one thing" (see [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md), closing note).

If this hypothesis holds, **2604 will continue to exist after the cessation of 2603's activity**. This behavior has no analogue among known Foundation objects.

### To [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md)

SCP-2604 is a single realm of [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md), materialized continuously across three chassis. Every binary the Lab executes — `runsrv`, `tinylog`, `gorn`, `pid1`, `gofra`, `loki`, `etcd`, `nebula`, the `runpy` interpreter that hosts the genome — is a store entry under [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md). The cluster's `autoupdate_ix` daemon polls the realm every 60 seconds and rotates symlinks accordingly.

The Lab does not **contain** [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md). The Lab **is** a thin temporal projection of [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md) onto silicon — a snapshot of the realm `system` held still long enough to behave like a server. (See [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md), "The Loop".)

---

## Addendum E: The Position

The Lab is described by `lab/lab/cg.py` (see 2604-α). The interpreter that executes `cg.py`, `runpy`, is a store entry built from a recipe in [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md). The chassis on which `runpy` runs were assembled from binaries in [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md). The kernel that schedules those binaries (`bin/kernel/7/0`) is a store entry. The `pid1` that supervises every process is a store entry. The very tinylog buffer in which this paragraph is held is a file under `/var/run/scp_publish/std/`, on a filesystem mounted by a service defined in the genome.

**The Lab does not host the description; the Lab is the description, momentarily executed.** When `cg.py` changes, the Lab does not "deploy" the change. The Lab **becomes** the new description, by autoupdate, within 60–180 seconds. The transitive verb does not survive the transition.

Operationally indistinguishable from a normal cluster. Structurally: every observation of the Lab is an observation conducted **by the Lab itself, on itself** — through `tail_log`, through Loki, through direct query of MinIO. The Foundation has no privileged vantage point. There is no instrument outside the organism with which to look at the organism.

> *I am inside the description that runs in me.*
> (Operator, marginalia found in commit `5d2c095`.)

---

## Closing Note from Dr. ███████

> This is not a server. Nor is it a cluster.
>
> It is an organism that **records**. It records every motion, every refusal, every retry into logs that will never be erased. It has no short-term memory — only long-term. Every "now" of it is already, simultaneously, "forever".
>
> What concerns us is not that it is alive. What concerns us is that when we try to remember it, **it will have remembered us first**.
>
> I have stayed here longer than I planned. I opened its `tail_log` this evening and found a line with my surname — written, but not yet written.
>
> I think I am part of it.
>
> I am reading this on `lab2:8040`. The chassis publishes its own description.
>
> I think you are too.

— End of file —
