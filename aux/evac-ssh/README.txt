Evacuation SSH on lab1

Service: EvacSsh in lab/cg.py, supervised as evac_ssh through the normal
commit/push/autoupdate deployment. Account: pg (UID/GID 2027).
Login: ssh -p 8101 pg@5.188.103.251
The WAN address above was read from the Xiaomi router on 2026-10-11.
Router rule evac_ssh_lab1: TCP 8101 -> 10.0.0.64:8101, persistent redirect
created with bin/xiaomi/api/xapi.py and activated via redirect_apply.
Also listens on lab1.mesh:8101. Passwords and root login are disabled.

Only the public key in the EvacSsh registration is authorized. Its fingerprint:
SHA256:it1w7y0MWB4hJm4DZqoOxXPaMQxco4LIu80+yywqy58
The server generates a separate persistent host key in /srv/evac-ssh.

Destinations relative to the SSH home (/home/pg):
  seagate-a/  UUID 6b194f91-10fc-4ad6-9f30-21581c641d56, about 3.78 TB free
  seagate-b/  UUID 2a39d5d3-80be-4b9c-bb99-0924d597c9e1, about 3.96 TB free
  hgst-a/     UUID 7b654717-6493-4534-90b5-c947fa8b7045, about 3.78 TB free
  hgst-b/     UUID 2617f25c-d4f5-4f38-acfe-c1cdd5250aed, about 3.78 TB free

These are four independent existing XFS filesystems, about 15.3 TB combined.
Each destination binds the filesystem's incoming-pg directory.
Old files and the active S3 partitions are left in place. There is no RAID.
Distribute the transfer across the directories; a file must fit one volume.

The service mounts by UUID in its own mount namespace on every start. It
refuses to listen if any filesystem or mount is unavailable. No formatting
or fallback to the root disk is performed. Only the four destination folders
are writable in the home; authorized_keys is managed by the service. The
home mounts and this key are not visible to the host's regular SSH daemon.

SFTP, scp and rsync are available. Example (run on the source host):
  rsync -a --partial --info=progress2 -e 'ssh -p 8101' \
    /source/batch-a/ pg@5.188.103.251:seagate-a/

For a reverse connection from the source host:
  ssh -NT -p 8101 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
    -R 127.0.0.1:18122:127.0.0.1:22 pg@5.188.103.251
The reverse listener is on lab1 loopback. Local forwarding is disabled.
Authentication to the source SSH server is separate from authentication to
evac_ssh; install the operator's public key on the source account first.

Inspect from an administrator session on lab1:
  cat /var/run/evac_ssh/std/current
  pid=$(pgrep -f '^dropbear .* /var/run/evac_ssh/dropbear.pid ')
  nsenter -t "$pid" -m -- df -h /home/pg/*
  nsenter -t "$pid" -m -- cat /home/pg/.ssh/authorized_keys

Removal: remove the EvacSsh registration through the usual deploy, then remove
only the evac_ssh_lab1 router redirect. Data directories persist on the disks.
