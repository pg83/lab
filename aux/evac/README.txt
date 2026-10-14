Historical VPN prototype, retained for the Keychain helper and experiments.
The completed merlin -> lab1 evacuation is documented in ../evac-transfer/README.txt
and did not use this VPN or the laptop. The supervised home.mesh VPN is the
set/pg/yandex/vpn overlay in the ix repository. The setup and measurements below
record the initial 2026-10-11 experiment, not the current deployment.

Evacuation setup, 2026-10-11

Data plane: source -> Yandex OpenVPN -> lab1 wired Ethernet -> existing XFS.
Authentication: OpenVPN management socket -> SSH via home -> work Keychain.
The Mac private key is not exported. The Mac must stay awake and its temporary
SSH server must remain available for TLS renegotiation (observed several minutes
apart). Bulk data does not travel through work or home.

Storage on lab1 (mounted read/write; write+sync probes passed):
  /srv/evac/seagate-a/incoming-evac-20261011  /dev/sdb2  ~3.78 TB free
  /srv/evac/seagate-b/incoming-evac-20261011  /dev/sdb3  ~3.96 TB free
  /srv/evac/hgst-a/incoming-evac-20261011     /dev/sdc1  ~3.78 TB free
  /srv/evac/hgst-b/incoming-evac-20261011     /dev/sdd1  ~3.78 TB free
Total: 15.3087 TB / 13.9232 TiB. These are four independent filesystems: split
objects larger than an individual volume or choose a suitable transfer layout.
No RAID; other source copy exists. Existing files and active S3 partitions remain.
Seagate has 64 reallocated sectors, zero pending/offline-uncorrectable sectors.

Inspect/remount after reboot:
  ssh root@lab1.mesh /srv/evac/storage.sh --check
  ssh root@lab1.mesh /srv/evac/storage.sh
There is no boot service for this temporary setup. UUIDs and mount guards are in
storage.sh. Check the destination mount before starting a transfer.

VPN runtime, profile and logs are under /srv/evac-vpn on lab1 (root-only).
Runtime: official openvpn_2.6.12-ya_22.04_amd64.deb, no installer execution.
URL: https://download.yandex.ru/hd/vpn/openvpn_2.6.12-ya_22.04_amd64.deb
SHA256: fabea1b8bd6cb5d64ca2ffb23800000663a040c8323e10a9b2be1e16da2cfcbc
Ubuntu Jammy libraries are extracted into a private runtime with an explicit
glibc loader; no host packages were installed. libc6 2.35-0ubuntu3.15 and
libssl3 3.0.2-0ubuntu1.30 came from jammy-security; package hashes were checked
against the HTTPS package index. iproute2 is bundled for macvlan support.
Public package/bootstrap files are in /home/pg/.cache/evac-vpn-research on home.
The protected client.ovpn contains CA/tls-auth material and is not in git.

vpn-network.sh creates separate network and mount namespaces, attaches a macvlan
to lab1 eth3, and obtains a DHCP lease. Current lease is 10.0.0.196; it may change.
DHCP stays running for lease renewal. OpenVPN routes and DNS are confined to
these namespaces. A root-only Unix socket carries the management protocol.

Start on lab1 (foreground, suitable for supervision):
  /srv/evac-vpn/vpn-network.sh
Keep this SSH session alive. Detached remote launches did not reliably survive
SSH logout on this host; nohup alone is not a supported deployment method here.
The network starts on management hold. Then start the signer bridge on home:
  python3 /home/pg/monorepo/lab/aux/evac/bridge.py \
    --key /home/pg/.cache/evac-work.ZsMlfeoA/id_ed25519 \
    --known-hosts /home/pg/.cache/evac-work.ZsMlfeoA/known_hosts
Keep the bridge process running too. The current setup uses two foreground
sessions; provision supervision when scheduling the actual evacuation.
Only initial Keychain approval needs --allow-keychain-ui. Normal operation fails
closed on a denied signature. SSH uses work 10.0.0.248:12345 via lab1; if the Mac's
DHCP address changes, update --mac and the temporary Dropbear listener.

Execute a downloader or diagnostic on lab1 inside the VPN:
  /srv/evac-vpn/vpn-exec.sh COMMAND ARGUMENTS...
Example via SSH:
  ssh root@lab1.mesh '/srv/evac-vpn/vpn-exec.sh ip addr show tun-evac'
Storage mount paths are visible inside this namespace.

Inspect protected VPN log:
  ssh root@lab1.mesh 'tail -20 /srv/evac-vpn/run/openvpn.log'
Stop the VPN/network:
  ssh root@lab1.mesh 'kill "$(cat /srv/evac-vpn/run/launcher.pid)"'
Stop the home bridge with SIGTERM; it shuts down OpenVPN before closing SSH.
Startup and bridge processes have no automatic restart policy. Downloads should
be resumable; verify size/checksums before declaring evacuation complete.

Keychain helper on work:
  ~/.local/libexec/evac/evac-keychain-signer --cn pg@ld.yandex.ru --no-ui self-test
Expected: RSA signature verified; private key was not exported.
Compiled with clang/Foundation/Security, ad-hoc signed. Rebuilding changes its
Keychain application identity and can require another approval. Self-test uses
raw public RSA recovery because SecKeyVerifySignature(RSA raw) behaved
inconsistently with the legacy Keychain certificate public key.

Tests:
  - Real VPN TLS 1.3 authentication and repeated renegotiations succeeded.
  - Keychain signature checked independently with Go against the certificate.
  - PSS SHA-256/384/512 with digest/max salt checked with Go crypto/rsa; malformed
    requests and incorrect digests rejected. Run:
      go build -o "${TMPDIR:-/tmp}/evac-pss-check" tests/pss-check.go
      python3 tests/check_pss.py "${TMPDIR:-/tmp}/evac-pss-check"
  - Namespace LAN throughput: 936 Mbit/s received, 5-second iperf3 from lab2.
  - mirror.yandex.ru/ubuntu/ls-lR.gz downloaded via tun-evac, IPv4:
      1 stream: 38,446,547 bytes / 9.612847 s = 32.0 Mbit/s
      4 streams: 153,786,188 bytes / 11.65 s = 105.6 Mbit/s
      16 streams: 615,144,752 bytes / 13.36 s = 368.35 Mbit/s
      32 attempts: 31 completed, 1 connection timeout; 1,191,842,957 bytes /
        21.59 s = 441.63 Mbit/s. VPN UDP receive-buffer errors reached 213.
  Client then changed to sndbuf/rcvbuf 8 MiB with matching server-push filters
  and fast-io. Linux reports 16 MiB effective socket buffers (doubled accounting).
      Final 32 streams: all completed; 1,230,289,504 bytes / 17.26 s =
        570.238 Mbit/s. UDP InErrors/RcvbufErrors/SndbufErrors all zero.
  SRV discovery selected a different gateway after the restart: 77.88.6.109
  instead of 77.88.6.110. The comparison does not isolate buffer tuning alone.
  These are public-mirror measurements, not the source cluster. Source address,
  format, permissions, real throughput and transfer/checksum strategy remain
  to be established when the source is supplied.

After evacuation: stop both processes, remove temporary SSH authorization/key
and Keychain helper as appropriate, and remove the protected VPN profile/runtime
when no longer needed. Do not delete or unmount incoming data as part of cleanup.
