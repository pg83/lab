# lab

Declarative description of a 3-node homelab (`lab1`, `lab2`, `lab3`), built and deployed with the [IX package manager](https://github.com/stal-ix/ix) ([PKGS.md](https://github.com/pg83/ix/blob/main/PKGS.md)).

Everything — the OS image, the services, the mesh network, the secondary IPs — is derived from a single cluster description generated in Python and materialized into IX packages via Jinja2 templates. There is no ad-hoc configuration; every host is a function of `lab/cg.py`.

## Layout

```
./ix                    # bootstrap: sets IX_PATH, execs ext/ix/ix
./ext/ix/               # IX package manager (git submodule, stal-ix/ix)
./lab/
    ix.sh               # top-level hub; pulls in lab/map with the generated cluster_map
    cg.py               # Python generator: hosts, ports, users, service classes, topology
    map/ix.sh           # per-host dispatch (extends lab/common + lab/hosts/<hostname>)
    common/ix.sh        # base package set for every host
    hosts/lab{1,2,3}/   # host-specific setup (disk mounts, extra users)
    etc/                # system config packages (ip/, hosts/, keys/, user/, env/, stopper/, certs/)
    services/
        sh/             # service-runner framework on top of runit
        autoupdate/     # git-pull + rebuild loop
        ci/             # builder loop driven by set/ci/tier/<n>
./bin/                  # homelab-specific IX packages (tools and services)
```

## How it runs

1. `./ix <command>` exports `IX_PATH="./:./ext/ix/pkgs"` and hands off to the IX tool.
2. `lab/ix.sh` executes `cg.py` to produce a `cluster_map` (hosts, ports, users, per-host service list).
3. The map is serialized and passed down to `lab/map`, which for each host loads `lab/common` + `lab/hosts/<hostname>`.
4. `lab/common` expands `hm.extra` — a list of `lab/services/sh(...)` package invocations, one per service.
5. Each service is realized as a runit-supervised script that base64-decodes a pickled Python object (`runpy` entry point) and calls its `.run()`.

Prometheus scrape targets and HAProxy/reproxy L7 rules are wired automatically: any service that implements `prom_port()` is added to the local `Collector` job list; any service yielding from `l7_balancer()` is added to `BalancerHttp` rules per host interface.

## Packages (`.sh` files)

The whole codebase is Jinja2 templates with a `.sh` extension. A package either extends `//die/hub.sh` (pure dependency hub — only declares `run_deps`) or `//die/gen.sh` (generates files into `${out}`). Dependencies are written as `path/to/pkg(param=value,param2=value)`.

Example (`lab/etc/ip/ix.sh`):

```jinja2
{% extends '//die/gen.sh' %}
{% block install %}
mkdir -p ${out}/etc/runit/1.d
cat << EOF > ${out}/etc/runit/1.d/20-{{ip_iface}}.sh
ip addr add {{ip_addr}} dev {{ip_iface}}
ip link set {{ip_iface}} up
route add default gw {{ip_gw}} {{ip_iface}}
resolvconf -u
EOF
{% endblock %}
```

## Hosts

Three physical hosts, each with four NICs (`eth0..eth3`, IPs `10.0.0.{64+4(n-1) .. +3}`), a Nebula overlay IP `192.168.100.{16,17,18}`, and a Nebula lighthouse `lh{1,2,3}` reachable on `5.188.103.251:424{2,3,4}`. Disk roles differ per host (`lab1:/dev/sda`, `lab2:LABEL=CI`, `lab3:LABEL=HOME`); additional per-host knobs live in `lab/hosts/lab{1,2,3}/ix.sh`.

## Services

All services are declared as Python classes in `lab/cg.py` and scheduled on hosts by `ClusterMap.it_cluster()`. Ports and UIDs come from the central maps in `do()`.

| Service | Port | User | Notes |
| --- | --- | --- | --- |
| `EtcdPrivate` | 8020/8021 | `etcd_private` | cluster-state KV on the Nebula overlay |
| `MinIO` ×3 | 8012 | `minio_{1,2,3}` | distributed S3, per-NIC instances, `LABEL=MINIO_{n}` xfs |
| `MinioConsole` | 8013 | `minio_console` | web UI on the Nebula IP |
| `DropBear` / `DropBear2` | 22 / 8023 | `root` | main + recovery SSH |
| `Collector` | 8008 | `collector` | Prometheus; scrape jobs auto-populated |
| `NodeExporter` | 8007 | `node_exporter` | |
| `NebulaNode` / `NebulaLh` | 4243 / 4242 | `root` / `nebula_lh` | overlay mesh + lighthouse |
| `Secrets` | 8022 | `secrets` | local HTTP; services fetch material via `get_key(path)` |
| `PersDB` | 8024 | `root` | small persistent KV |
| `BalancerHttp` | 8080 | `balancer_http` | reproxy; rules yielded by `l7_balancer()` |
| `SocksProxy` + `SshTunnel` ×N | 8015 + 8017/8018 | `socks_proxy`, `ssh_*_tunnel` | egress aggregation over SSH SOCKS5 |
| `WebHooks` | 8005 | `web_hooks` | CGI server for git hooks (`webhook.homelab.cam`) |
| `SftpD` | 8002 | `sftp_d` | SFTP frontend backed by MinIO |
| `SecondIP` ×2 | — | `root` | etcd-locked floating IPs (`10.0.0.32/24`, `10.0.0.33/24`) |
| `IPerf` | 8006 | `root` | |
| `CO2Mon` | 8019 | `root` | |
| `MirrorFetch` / `HFSync` / `GHCRSync` | — | `mirror_fetch` / `hf_sync` / `ghcr_sync` | etcd-locked sync loops |
| `CI` | — | `ci` | per-host `set/ci/tier/<n>` build loop (see `CI_MAP`) |

## Secrets

Secrets are served locally by the `Secrets` service on `localhost:8022`. Code never embeds material; it calls `get_key('/path')` at runtime (`/nebula/ca.crt`, `/s3/user`, `/hf/token`, `/ghcr/token`, `/tunnel/<name>`, ...). The backing store is external to this repo.

## Updating

`lab/services/autoupdate` runs a loop as user `ix` that pulls the repo and rebuilds via IX. `lab/services/ci` watches `etcd` (`git_ci` topic) and triggers `./ix build bld/all` + `./ix mut ci <targets> --jail=1 --seed=1 --tmpfs=1`.
