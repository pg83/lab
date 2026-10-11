#!/usr/bin/env python3
"""lab1 servant: reconcile merlin's worker without tying it to an SSH session."""
import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time


def save_json(path, value):
    temp = path.with_suffix(".tmp")
    with temp.open("w") as out:
        json.dump(value, out, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def ssh(state, command):
    return ["ssh", "-F", "/dev/null", "-T", "-i", str(state / "source-id"),
            "-p", "18122", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", "HostKeyAlias=merlin.klg.yp-c.yandex.net",
            "-o", "UserKnownHostsFile=" + str(state / "source-known_hosts"),
            "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=2", "pg@127.0.0.1", command]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="/srv/evac-transfer")
    args = parser.parse_args()
    os.umask(0o077)
    state = Path(args.state)
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (state / "controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan_file = state / "plan.json"
        if not plan_file.exists():
            save_json(plan_file, {"enabled": True, "start": 200, "end": 249,
                                  "uploads": 4, "lanes": 8, "chunk_mib": 64, "keep_source": False})
        # Read this deployment's files once: an update gets a new servant.
        code = Path("/bin/evac-transfer").read_bytes()
        agent = Path("/bin/evac-transfer-source-agent").read_bytes()
        installed, last_tail, last_service = False, [], None
        while True:
            try:
                plan = json.loads(plan_file.read_text())
                if not installed:
                    subprocess.run(ssh(state, "umask 077; mkdir -p ~/.local/lib/evac-transfer && "
                                       "cat > ~/.local/lib/evac-transfer/source-agent.py.new && "
                                       "mv ~/.local/lib/evac-transfer/source-agent.py.new "
                                       "~/.local/lib/evac-transfer/source-agent.py"),
                                   input=agent, check=True, timeout=45)
                    installed = True
                payload = {"plan": plan, "worker_b64": base64.b64encode(code).decode()}
                result = subprocess.run(ssh(state, "python3 ~/.local/lib/evac-transfer/source-agent.py"),
                                        input=json.dumps(payload).encode(), stdout=subprocess.PIPE,
                                        check=True, timeout=110)
                status = json.loads(result.stdout)
                status.update(checked_at=time.time(), connected=True, plan=plan)
                save_json(state / "status.json", status)
                summary = {**status["service"], "completed": len(status["completed"]),
                           "total": plan["end"] - plan["start"] + 1}
                if summary != last_service:
                    print(json.dumps(summary), flush=True)
                    last_service = summary
                for line in status["tail"]:
                    if line not in last_tail:
                        print(line, flush=True)
                last_tail = status["tail"]
            except Exception as error:
                installed = False
                message = str(error)
                print(time.strftime("%Y-%m-%d %H:%M:%S"), "Waiting for source:", message, flush=True)
                status_path = state / "status.json"
                old = json.loads(status_path.read_text()) if status_path.exists() else {}
                save_json(status_path, {**old, "connected": False, "checked_at": time.time(), "error": message})
            time.sleep(20)


if __name__ == "__main__":
    main()
