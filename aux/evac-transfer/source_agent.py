#!/usr/bin/env python3
"""Reconcile a persistent user service on merlin; called by lab1's servant."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def replace_if_changed(path, data, mode=0o600):
    path = Path(path)
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            os.fchmod(out.fileno(), mode)
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return True


def worker_unit(home, script, plan):
    if not 0 <= plan["start"] <= plan["end"] <= 499:
        raise ValueError("Allowed range is 0..499")
    if not 1 <= plan["uploads"] <= 4 or not 1 <= plan["lanes"] <= 32:
        raise ValueError("Invalid concurrency")
    if not 1 <= plan["chunk_mib"] <= 256:
        raise ValueError("Invalid chunk size")
    compression = plan.get("compression", "zstd")
    if compression not in ("none", "lz4", "zstd"):
        raise ValueError("Invalid compression")
    zstd_level = plan.get("zstd_level", 4)
    if type(zstd_level) is not int or not 1 <= zstd_level <= 19:
        raise ValueError("Invalid Zstd level")
    # Only fixed paths and checked integers enter the systemd command line.
    options = " ".join("--%s %d" % (name.replace("_", "-"), plan[name])
                       for name in ("start", "end", "uploads", "lanes", "chunk_mib"))
    if plan.get("keep_source", False):
        options += " --keep-source"
    options += " --compression " + compression
    options += " --zstd-level %d" % zstd_level
    return f"""[Unit]
Description=Plutonium evacuation managed by lab1
StartLimitIntervalSec=0

[Service]
Type=exec
WorkingDirectory={home}
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 {script} run {options} --remote-helper /bin/evac-transfer
Restart=on-failure
RestartSec=30
RemainAfterExit=yes
KillMode=mixed
TimeoutStopSec=60
UMask=0077
StandardOutput=append:{home}/.cache/evac-transfer/pipeline/service.log
StandardError=inherit

[Install]
WantedBy=default.target
""".encode()


def reconcile(payload, home=None):
    home = Path.home() if home is None else Path(home)
    plan = payload["plan"]
    code = base64.b64decode(payload["worker_b64"], validate=True)
    version = hashlib.sha256(code).hexdigest()
    script = home / ".local/lib/evac-transfer" / ("transfer-" + version + ".py")
    replace_if_changed(script, code, 0o700)
    replace_if_changed(home / "down2.py", code, 0o700)
    state = home / ".cache/evac-transfer/pipeline"
    state.mkdir(parents=True, exist_ok=True)
    unit_path = home / ".config/systemd/user/evac-transfer.service"
    changed = replace_if_changed(unit_path, worker_unit(home, script, plan))
    ctl = ["systemctl", "--user"]
    if changed:
        subprocess.run([*ctl, "daemon-reload"], check=True)
    # A disabled plan persists over source reboot as well as lab restarts.
    if plan.get("enabled", True):
        subprocess.run([*ctl, "enable", "evac-transfer.service"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([*ctl, "restart" if changed else "start", "evac-transfer.service"], check=True)
    else:
        subprocess.run([*ctl, "disable", "--now", "evac-transfer.service"], check=True,
                       stdout=subprocess.DEVNULL)
    service = subprocess.check_output([*ctl, "show", "evac-transfer.service", "--property",
                                      "ActiveState,SubState,MainPID,NRestarts,ExecMainStatus"], text=True)
    completed = []
    for path in sorted(state.glob("banners_remote-*.uploaded.json")):
        result = json.loads(path.read_text())
        index = int(result["namespace"].rsplit("-", 1)[1])
        if plan["start"] <= index <= plan["end"]:
            completed.append({k: result[k] for k in ("namespace", "snapshot", "bytes", "sha256", "volume")})
    logfile = state / "service.log"
    tail = []
    if logfile.exists():
        with logfile.open("rb") as log:
            log.seek(max(0, logfile.stat().st_size - 8192))
            tail = log.read().decode(errors="replace").splitlines()[-12:]
    return {"service": dict(line.split("=", 1) for line in service.splitlines()),
            "version": version, "completed": completed, "tail": tail}


if __name__ == "__main__":
    os.umask(0o077)
    print(json.dumps(reconcile(json.load(sys.stdin))), flush=True)
