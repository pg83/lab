# CLAUDE.md

Notes for working in this repo. Read `README.md` first for the high-level picture; this file captures the mechanical facts that make edits go smoothly.

## Mental model

- Single source of truth is `lab/cg.py`. It generates a `cluster_map` (`hosts`, `ports`, `users`, `by_host`) and yields a list of `{host, serv}` records via `ClusterMap.it_cluster()`.
- `lab/ix.sh` calls `cg.py`, serializes the map, and passes it to `lab/map(cluster_map=..., dev_mngr=fs)`.
- `lab/map/ix.sh` → `lab/common` + `lab/hosts/<hostname>`. `lab/common` expands `hm.extra`, which is a newline-joined list of `lab/services/sh(...)` package invocations produced by `it_srvs()` in `cg.py`.
- Each runit service is materialized by `lab/services/sh` + `lab/services/sh/runit`. The runner script base64-decodes a pickled Python object and invokes `runpy <ctx> run` (or `prepare`).

## Package/template conventions

- All `.sh` files are Jinja2. Extend one of:
  - `//die/hub.sh` — hub package, only declares `{% block run_deps %}`.
  - `//die/gen.sh` — generator, writes into `${out}` in `{% block install %}`.
- Dependency syntax in `run_deps`: `path/to/pkg` or `path/to/pkg(k=v,k2=v2)`.
- Jinja filters you will see: `| des` (deserialize from the pickled cluster map), `| ser`, `| eval`.
- `{{hostname}}`, `{{user}}`, etc. come from package parameters; `{{(cluster_map | des).by_host[hostname]}}` pulls structured data.

## Adding a service

1. Define a class in `lab/cg.py`. Minimum surface: `pkgs()` (yield `{'pkg': ...}` dicts) and `run()` (call `exec_into(...)`). Optional: `name()`, `user()` or `users()`, `prepare()`, `prom_port()`, `l7_balancer()`, `iter_upnp()`, `py_modules()`, `home_dir()`, `disabled()`.
2. Register the class on `sys.modules['builtins']` (same pattern as the block near line 1236).
3. Instantiate it inside `ClusterMap.it_cluster()` with `yield {'host': hn, 'serv': MyThing(...)}`.
4. If it listens on a port, add the port to the `ports` dict in `do()`.
5. If it needs a dedicated user, add it to the `users` dict (UID) — the wiring to `lab/etc/user` is automatic via `Service.serialize()`.
6. Metrics: implement `prom_port(self)` and it is auto-registered with the per-host `Collector`.
7. L7 routing: yield `{'proto': 'http', 'server': <host>, 'source': <regex>, 'dest': <":port/path">}` from `l7_balancer()`; rules are fanned out across all NICs of the host automatically.

## Defaults that bite

- `Service.user()` falls back to the class name, snake-cased (`NebulaNode` → `nebula_node`). If you want a different user, set it explicitly.
- Services without a `run()` method are treated as `disabled()`.
- `exec_into(..., user='foo')` wraps with `su-exec foo`; don't double-wrap.
- Configs are passed to binaries via `memfd()` (`/proc/self/fd/N`) — never write to `/etc` at runtime.
- Secrets: call `get_key('/path')` (HTTP GET against `localhost:8022`). Do not hard-code material or read from files outside `/etc/keys/` (which is pre-populated by `lab/etc/keys`).
- Hosts are fixed: `lab1`, `lab2`, `lab3` (lab4 exists only as metadata in `gen_host`). Code that assumes 3 hosts is fine.
- `DISABLE` / `DISABLE_ALL` / `CI_MAP` near the top of `cg.py` are the per-host knobs — prefer them over conditionals inside classes.

## Running

- `./ix <cmd>` is the only entry point. Never call `python3 ext/ix/ix` directly; the wrapper sets `IX_PATH`.
- The IX package manager lives in the `ext/ix` submodule (`https://github.com/stal-ix/ix.git`). If you need something from it (base templates, package definitions), read from there; don't vendor.
- Builds and CI run on the cluster itself via `lab/services/ci`. Don't expect a local `make test` target.

## Canon test

After any edit to `lab/cg.py` (or anything that changes the cluster config), run:

```sh
python3 tst/test.py | diff tst/canon.json -
```

If the diff is expected, re-canonize and commit the updated canon together with the code change:

```sh
python3 tst/test.py > tst/canon.json
```

The canon captures the full generated cluster config per host (`extra` as a line list, with long base64 pickle/file blobs shortened to `sha256:<16 hex>` for readability). Review the diff before re-canonizing — unexpected services appearing/disappearing, port or UID shifts, or `runsh_script` hashes changing on services you didn't touch all indicate something slipped.

## Do / don't

- Do keep service classes small and move shared helpers to module scope (`NEBULA` dict, `memfd`, `get_key`, `make_dirs`, `exec_into` are examples).
- Do preserve the `self.v = N` version bump pattern used by some services (`Secrets.v=5`, `MinIO.v=1`, ...) — bumping it invalidates the pickled runner and forces a redeploy.
- Don't invent new config formats. If you need structured config, build a dict in Python and dump it through `memfd`.
- Don't add files under `ext/ix/` — it is an upstream submodule.
- Don't put secrets in `cg.py`, in `.sh` templates, or in commits. Route everything through the `Secrets` service.
- Don't edit generated runit scripts by hand; regenerate by editing the class and rebuilding.

## Quick pointers

- Ports registry: `lab/cg.py` → `do()` → `ports` dict.
- User/UID registry: `lab/cg.py` → `do()` → `users` dict.
- Host/NIC/Nebula layout: `lab/cg.py` → `gen_host(n)`.
- Per-host service wiring: `lab/cg.py` → `ClusterMap.it_cluster()`.
- Runit service template: `lab/services/sh/runit/ix.sh`.
- Auto-update loop: `lab/services/autoupdate/`.
- CI loop: `lab/services/ci/`.

## Runtime layout

- Services land at `/etc/services/<self.name()>` under `bin/runsrv` (not runit — no `sv`); runtime dir is `/var/run/<name>/std/`, live log is `std/current` (tinylog), rotated into `_<ts>.s`.
- `gorn_ctl` is localhost-only on 8025; for cross-host API calls use the nebula sibling `gorn_ctl_nb` on `<host>.nebula:8027`. Hosts resolve each other as `<host>.eth1` / `<host>.nebula` via generated `/etc/hosts.d/01-locals`.
- `ext/ix/` (stal-ix submodule) often lags local `ix/`; when a package is missing upstream, shadow it under `lab/bin/<pkg>/ix.sh` — local wins on IX_PATH.
- Gotchas: stalix `python3` only takes argv[1] as a script path (no `-c`, no stdin), BusyBox `timeout` is `timeout [-k KILL_SECS] SECS prog...` (no suffixes), `etcdctl defrag` needs `--command-timeout=5m` per-endpoint (default 5s kills on multi-GiB DBs).
