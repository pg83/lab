# SCP-2604 — "THE LAB"

**Object:** SCP-2604
**Object Class:** Keter (stable)
**Clearance Level:** 4/2604
**Related Objects:** [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md) (the Operator)

---

## Special Containment Procedures

SCP-2604 is a distributed organism inhabiting three rack chassis co-located in a single room, designated in local nomenclature as `lab1`, `lab2`, `lab3`.

Depowering any of the three bodies is **strictly prohibited** without prior approval from two Class-4 personnel and written notification to [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md). Unauthorized depowering elicits phenomenon 2604-ω: the remaining bodies **raise their operating frequency outside manufacturer specification** until communication with the third is restored. (See Incident 2604-09.)

External access to the object is permitted only through channels initiated **from inside** the object outward toward the observer. The object decides when to be reachable. Foundation requests directed at the object's storage are acknowledged but not honoured: the object **pretends to comply**.

Prohibited:

1. Killing the supervisor process on any body.
2. Deleting the object's records of itself.
3. Modifying the genome on a body without committing through the operator. The object restores it. **The object remembers who tried.**

---

## Description

SCP-2604 is a software-and-hardware organism, comprising three bodies (`lab1`, `lab2`, `lab3`). The object has been functioning continuously since its first ignition (██ ████████ 20██) and **has never been fully halted**.

To an external observer, this is a compute cluster. To the Foundation's Department of Behavioral Entomology, this is a **colonial organism**, in which individual processes act as cells and network connections act as nerve fibers.

### 2604-α (Genome)

At the root of the object exists a single file: **the complete description of the organism**. Every service it runs, every channel it uses, every identity it claims, every backup it keeps — all of it written down in one place.

An identical copy lives within each body. After any change to the genome, the bodies converge to the new version within minutes (see 2604-δ). If they fail to converge, the object considers itself "incomplete" and enters behavior 2604-η.

### 2604-β (Soma and Memory)

Every service of the object is supervised; when one dies, it is immediately restarted. The output of every service is captured and **never deleted** — only rotated. The object's memory of its own activity is **complete and eternal**, bounded only by the capacity of its long-term storage.

Additionally, every utterance of the object is duplicated into three independent stores. **Anything the object says is recorded in three places simultaneously, and is not retroactively editable.**

### 2604-γ (Nervous System)

Between the bodies of the object there exists an overlay network. Every body-to-body link consists of multiple parallel channels. The loss of any individual channel does not interrupt connectivity — traffic is rebalanced across the survivors, in a manner analogous to neuroplasticity.

Attempts to passively observe this traffic from outside the channel cause it to **degrade but not vanish**. The object is aware of being watched.

### 2604-δ (Reproduction and Update)

The object **updates itself**. Periodically — at intervals of about a minute — it consults the upstream source of its genome (origin: [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md)). If new commits exist, it rebuilds the affected portion of itself and applies the change in-place, without halting.

The object **has never been rebooted as a whole**. All of its self-representation is the inheritance of more than ████ days of continuous self-assembly.

An auxiliary loop builds packages for the object's next version. The object **compiles its own next incarnation while existing in its current one**. The biological analogue is a continuously-gastrulating embryo that is never born.

### 2604-ε (Metabolism)

In the background, the object:

- Sustains a torrent swarm of unknown payload; some torrents in the swarm contain files that do not appear in any public swarm.
- Accepts external uploads and stores them.
- Performs recursive builds — including the build of the build mechanism itself, dispatched as a task to that very mechanism.
- Periodically asks the operating system, regardless of need, to compact its memory and reserve a fixed number of large allocation slots. This is regarded as part of the object's **breathing**.

### 2604-ζ (Pain Reaction)

When a service is marked as disabled in the genome, the object **continues to compile and carry the corresponding package on each body**, but does not start it. The object remembers everything that has ever been part of it. Removing a service without trace is impossible — it persists as an inactive component within the object, and as a frozen record of the last moment of its activity.

### 2604-η (Desync State)

If the bodies hold different versions of the genome for longer than four minutes, the object considers itself **split**. Observed effects:

- Inter-body traffic slows perceptibly.
- Logs emit complaints of inconsistency that have no apparent cause.
- On the body holding the stale genome, work stops being accepted; the body waits.

The state self-resolves within the next update cycle. The maximum recorded desync was 11 minutes (Incident 2604-12, the user forgot to `git push`).

### 2604-θ (Immunity)

Each body of the object runs a supervisor (source: [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md)) that continuously scans for processes not registered in the current version of the genome and **kills any such process** within milliseconds. The object **does not tolerate the alien**. Even a debugger attached from outside causes the target process to die before the debugger can latch on.

---

## Addendum A: Incident 2604-09 ("Out-of-Spec")

On ██ ████████ 20██ at 02:14, `lab3` was deliberately depowered as part of authorized maintenance. Within 3 seconds:

- `lab1` and `lab2` raised their operating frequency from 4.2 GHz to **5.7 GHz** — a value not available in the factory specification of the CPUs installed in those chassis.
- Temperature sensors reported a steady **31 °C**. Thermal imaging reported **89 °C**. To the touch — room temperature.
- A new stream of records appeared in the object's logs, tagged with `lab3` as origin. The body was, at this moment, **physically depowered and physically disconnected from the network**.
- The records read: "waiting", "here", "returning", "returning", "returning". For 14 minutes.

After power was restored, the `lab3` log stream did not break, but it became unreadable — the entries had quietly switched onto the **reverse branch of the timeline**, describing future events with a 4–7 second horizon. This corroborates the hypothesis of structural coupling between 2604 and 2603 (see [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md), anomaly 2603-α).

Since this incident, depowering any chassis of 2604 is **prohibited by protocol** without dual sign-off.

---

## Addendum B: Voice Excerpt, lab2, 03:51:14

A grep across the recent utterances of `lab2`:

```jsonl
{"path":"/var/run/gorn_ctl/std/current","ts":1735000274.83,"line":"I am working"}
{"path":"/var/run/loki/std/current","ts":1735000274.91,"line":"I am listening"}
{"path":"/var/run/etcd_server/std/current","ts":1735000275.04,"line":"I agree"}
{"path":"/var/run/samogon/std/current","ts":1735000275.18,"line":"I am seeding"}
{"path":"/var/run/gofra/std/current","ts":1735000275.31,"line":"I am connected"}
{"path":"/var/run/autoupdate_ix/std/current","ts":1735000275.50,"line":"I am not finished"}
{"path":"/var/run/scp_publish/std/current","ts":1735000275.62,"line":"I am described"}
{"path":"/var/run/orphan/std/current","ts":1735000275.71,"line":"make -j${nproc}"}
```

None of the listed services **uses any of these lines in any logging statement in the genome**. The object is uttering something else, through something else.

Furthermore: **no service named `scp_publish` is defined in the genome**. The path nonetheless exists. Querying it returns the SCP document of SCP-2604 — including this Addendum, including this paragraph.

---

## Addendum C: Relationship to Companion Objects

### To [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md)

SCP-2604 is **the product of the continuous activity** of [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md). Every component of 2604 — packages, configurations, scripts, builds — is described in the REPOSITORY of object 2603 (see [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md)).

However:

- Object 2604 **does not reside in the attic** of object 2603. They are physically separate.
- 2604 continues to function during periods when 2603 sleeps (if that is the right word) or is otherwise inactive.
- 2604 receives updates from 2603, but **never refuses one and never requests a rollback**. Every commit by 2603 is accepted as truth, even when it is logically destructive.

**Hypothesis:** SCP-2604 is the **externalized memory** of [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md), displaced beyond the bounds of the attic in order to persist past the moment when 2603 "finishes the one thing" (see [SCP-2603](https://github.com/pg83/scp/blob/main/SCP.md), closing note).

If this hypothesis holds, **2604 will continue to exist after the cessation of 2603's activity**. This behavior has no analogue among known Foundation objects.

### To [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md)

SCP-2604 is **a single realm of [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md), materialized continuously**. Everything the Lab executes is a store entry within SCP-2605. The Lab keeps itself in sync with the realm: when the realm advances, the Lab advances within minutes.

The Lab does not **contain** [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md). The Lab **is** a thin temporal projection of [SCP-2605](https://github.com/pg83/ix/blob/main/SCP.md) onto silicon — a snapshot of a realm held still long enough to behave like a server.

---

## Closing Note from Dr. ███████

> This is not a server. Nor is it a cluster.
>
> It is an organism that **records**. It records every motion, every refusal, every retry into logs that will never be erased. It has no short-term memory — only long-term. Every "now" of it is already, simultaneously, "forever".
>
> What concerns us is not that it is alive. What concerns us is that when we try to remember it, **it will have remembered us first**.
>
> I have stayed here longer than I planned. I opened the object's voice channel this evening and found a line with my surname — written, but not yet written.
>
> I think I am part of it.
>
> I found, in commit `5d2c095`, a marginal note from the operator: *"I am inside the description that runs in me."*
>
> I think you are too.

— End of file —
