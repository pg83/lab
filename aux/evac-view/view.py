#!/usr/bin/env python3
"""Read-only evacuation monitor; privileged collector, unprivileged HTTP server."""
import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time

VOLUMES = ("seagate-a", "seagate-b", "hgst-a", "hgst-b")
FIRST, LAST = 0, 499
PUBLIC = Path("/var/run/evac_view_data/public/status.json")
SOURCE_PROBE = r'''
import json, os
from pathlib import Path
home = Path.home()
base = home / '.cache/evac-transfer/pipeline'
disk = os.statvfs(home / 'banners_remote')
def indices(suffix):
    return sorted(int(p.name.split('.')[0].rsplit('-', 1)[1])
                  for p in base.glob('banners_remote-*.' + suffix))
print(json.dumps({'free_bytes': disk.f_bavail * disk.f_frsize,
                  'total_bytes': disk.f_blocks * disk.f_frsize,
                  'ready': indices('download.json'),
                  'downloading': indices('downloading.json')}))
'''


def read_json(path):
    # Only tiny, explicitly selected state files; never read an archive/key.
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("Oversized state file")
    return json.loads(path.read_text())


def safe_record(path):
    value = read_json(path)
    match = re.fullmatch(r"banners_remote-(\d+)", value.get("namespace", ""))
    if not match or not FIRST <= int(match[1]) <= LAST:
        raise ValueError("Invalid shard")
    if not isinstance(value.get("bytes"), int) or value["bytes"] < 0:
        raise ValueError("Invalid byte count")
    if not re.fullmatch(r"[0-9a-f]{64}", value.get("sha256", "")):
        raise ValueError("Invalid digest")
    compression = value.get("compression", "none")
    if compression not in ("zstd", "lz4", "none"):
        raise ValueError("Invalid compression")
    # A whitelist: session directories, source paths and raw logs stay private.
    return {"id": int(match[1]), "bytes": value["bytes"],
            "sha256": value["sha256"], "compression": compression,
            "updated_at": path.stat().st_mtime}


def destination_roots():
    # /proc/PID/root resolves inside the supervised SSH daemon's mount namespace,
    # including after reboot when the initial /srv/evac mounts no longer exist.
    pid = subprocess.check_output(
        ["pgrep", "-o", "-f", r"^dropbear .* /var/run/evac_ssh/dropbear.pid "],
        text=True, timeout=5).strip()
    base = Path("/proc") / pid / "root/home/pg"
    return {name: base / name for name in VOLUMES}


def scan_volumes(roots):
    shards, volumes, issues = {}, [], []
    for name in VOLUMES:
        root = roots.get(name)
        volume = {"name": name, "available": False}
        try:
            if root is None or root.stat().st_dev == root.parent.stat().st_dev:
                raise ValueError("Destination is not mounted")
            disk = os.statvfs(root)
            volume.update(available=True, free_bytes=disk.f_bavail * disk.f_frsize,
                          total_bytes=disk.f_blocks * disk.f_frsize)
            folder = root / "banners_remote"
            for path in sorted(folder.glob("banners_remote-*.json")):
                if path.is_symlink():
                    continue
                try:
                    checkpoint = path.name.endswith(".transfer.json")
                    record = safe_record(path)
                    archive = path.name.removesuffix(".transfer.json" if checkpoint else ".json")
                    payload = folder / (archive + ".partial" if checkpoint else archive)
                    if not checkpoint:
                        if payload.is_symlink() or payload.stat().st_size != record["bytes"]:
                            raise ValueError("Archive differs from receipt")
                    elif not payload.exists():
                        # Completed checkpoints remain next to the final receipt.
                        continue
                    elif payload.is_symlink() or payload.stat().st_size < record["bytes"]:
                        raise ValueError("Archive is shorter than checkpoint")
                    record.update(volume=name, archive=archive, complete=not checkpoint)
                    old = shards.get(record["id"])
                    if old and old["archive"] != archive:
                        raise ValueError("Duplicate shard archive")
                    if not old or record["complete"]:
                        shards[record["id"]] = record
                except (OSError, ValueError, TypeError, KeyError):
                    issues.append({"kind": "archive", "volume": name})
        except (OSError, ValueError):
            issues.append({"kind": "volume", "volume": name})
        volumes.append(volume)
    return shards, volumes, issues


class SourceProbe:
    def __init__(self, state):
        self.state = state
        self.value = {"available": False}

    def run(self):
        while True:
            ssh = ["ssh", "-F", "/dev/null", "-T", "-i", str(self.state / "source-id"),
                   "-p", "18122", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                   "-o", "StrictHostKeyChecking=yes", "-o", "HostKeyAlias=merlin.klg.yp-c.yandex.net",
                   "-o", "UserKnownHostsFile=" + str(self.state / "source-known_hosts"),
                   "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=5",
                   "-o", "ServerAliveCountMax=2", "pg@127.0.0.1", "python3 -"]
            try:
                result = subprocess.run(ssh, input=SOURCE_PROBE, text=True, capture_output=True,
                                        check=True, timeout=20)
                raw = json.loads(result.stdout)
                self.value = {"available": True, "checked_at": time.time(),
                              "free_bytes": int(raw["free_bytes"]),
                              "total_bytes": int(raw["total_bytes"]),
                              "ready": [n for n in raw["ready"] if FIRST <= n <= LAST],
                              "downloading": [n for n in raw["downloading"] if FIRST <= n <= LAST]}
            except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
                self.value = {**self.value, "available": False}
            time.sleep(30)


class Monitor:
    def __init__(self):
        self.samples = deque(maxlen=8)
        self.history = deque(maxlen=180)

    def snapshot(self, status, records, volumes, source, issues, now):
        checked = float(status.get("checked_at", 0))
        connected = bool(status.get("connected")) and 0 <= now - checked < 90
        service = status.get("service", {})
        running = connected and service.get("ActiveState") == "active" and service.get("SubState") == "running"
        staging_fresh = source.get("available", False) and now - source.get("checked_at", 0) < 90
        counts = {n: records.get(n, {}).get("bytes", 0) for n in range(FIRST, LAST + 1)}
        good_sample = all(v["available"] for v in volumes) and not issues
        if not good_sample or (self.samples and any(counts[n] < self.samples[-1][1][n] for n in counts)):
            self.samples.clear()
        rates = {}
        window = None
        if good_sample:
            if self.samples:
                then, old = self.samples[0]
                if now > then:
                    window = now - then
                    rates = {n: max(0, counts[n] - old[n]) * 8 / (now - then) / 1e6 for n in counts}
            self.samples.append((now, counts))
        shards = []
        for n in range(FIRST, LAST + 1):
            record = records.get(n, {})
            phase = "waiting"
            if staging_fresh and n in source.get("downloading", []):
                phase = "downloading"
            if staging_fresh and n in source.get("ready", []):
                phase = "ready"
            if record:
                phase = "uploading" if running and now - record["updated_at"] < 120 else "paused"
            if record.get("complete"):
                phase = "complete"
            shards.append({"id": n, "bytes": counts[n], "phase": phase,
                           "mbps": rates.get(n),
                           **{k: record[k] for k in ("volume", "archive", "compression", "updated_at") if k in record},
                           **({"sha256": record["sha256"]} if record.get("complete") else {})})
        completed = sum(s["phase"] == "complete" for s in shards)
        rate = sum(rates.values()) if rates else None
        self.history.append({"at": now, "mbps": rate})
        warnings = []
        if not connected:
            warnings.append("Нет свежей связи с источником")
        elif not running and completed < LAST - FIRST + 1:
            warnings.append("Сервис передачи сейчас не работает")
        if any(s["phase"] == "paused" for s in shards):
            warnings.append("Есть незавершённые архивы без свежего прогресса")
        if not staging_fresh:
            warnings.append("Место на источнике: нет свежих данных")
        elif source["free_bytes"] < 20 * 1024**3:
            warnings.append("На источнике осталось меньше резерва 20 GiB")
        for v in volumes:
            if not v["available"]:
                warnings.append(v["name"] + ": раздел недоступен")
            elif v["free_bytes"] < 50 * 1024**3:
                warnings.append(v["name"] + ": осталось меньше 50 GiB")
        if any(i["kind"] == "archive" for i in issues):
            warnings.append("Есть архив с некорректной квитанцией или checkpoint")
        return {"generated_at": now, "source_checked_at": checked,
                "connected": connected, "running": running,
                "service": {k: service.get(k) for k in ("ActiveState", "SubState", "NRestarts")},
                "summary": {"completed": completed, "total": LAST - FIRST + 1,
                            "bytes": sum(counts.values()), "mbps": rate,
                            "window_seconds": window,
                            "active": sum(s["phase"] == "uploading" for s in shards)},
                "volumes": volumes, "shards": shards, "warnings": warnings,
                "source": {k: source[k] for k in ("free_bytes", "total_bytes", "checked_at") if k in source}
                          | {"available": staging_fresh},
                "history": list(self.history)}


def collect(args):
    args.data.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    monitor = Monitor()
    probe = SourceProbe(args.state)
    threading.Thread(target=probe.run, daemon=True).start()
    while True:
        try:
            status = read_json(args.state / "status.json")
        except (OSError, ValueError):
            status = {}
        try:
            roots = destination_roots()
        except (OSError, subprocess.SubprocessError):
            roots = {}
        records, volumes, issues = scan_volumes(roots)
        data = monitor.snapshot(status, records, volumes, probe.value, issues, time.time())
        temporary = args.data.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False) + "\n")
        temporary.chmod(0o644)
        temporary.replace(args.data)
        time.sleep(5)


def handler(data_path, assets):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EvacView"

        def do_GET(self):
            route = self.path.split("?", 1)[0]
            status = 200
            if route == "/api/status":
                mime = "application/json; charset=utf-8"
                try:
                    body = data_path.read_bytes()
                except OSError:
                    status, body = 503, b'{"error":"Status not ready"}'
            elif route in ("/", "/app.js", "/style.css"):
                filename = "index.html" if route == "/" else route[1:]
                mime = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8",
                        "style.css": "text/css; charset=utf-8"}[filename]
                body = (assets / filename).read_bytes()
            else:
                status, mime, body = 404, "text/plain", b"Not found\n"
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        do_HEAD = do_GET

        def log_message(self, *args):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "serve"))
    parser.add_argument("--state", type=Path, default=Path("/srv/evac-transfer"))
    parser.add_argument("--data", type=Path, default=PUBLIC)
    # Pin assets to the same immutable package as this running executable.
    parser.add_argument("--assets", type=Path,
                        default=Path(__file__).resolve().parent.parent / "share/evac-view")
    parser.add_argument("--listen", default="127.0.0.1:8102")
    args = parser.parse_args()
    if args.command == "collect":
        collect(args)
    else:
        host, port = args.listen.rsplit(":", 1)
        server = ThreadingHTTPServer((host, int(port)), handler(args.data, args.assets))
        server.daemon_threads = True
        print("Evacuation view listening on " + args.listen, flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
