#!/usr/bin/env python3
"""Bounded Plutonium -> streaming tar -> parallel SSH -> sequential HDD pipeline."""
import argparse
import concurrent.futures as cf
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shlex
import shutil
import signal
import subprocess as sp
import sys
import tempfile
import threading
import time

GIB = 1024 ** 3
MIB = 1024 ** 2
VOLUMES = ("seagate-a", "seagate-b", "hgst-a", "hgst-b")
YT_FS = "//home/plutonium/reactor/filesystems/plutonium-in-yabs-stable/stable"
YT_WORKER = "//home/saas2/prod/yabs/worker"
REMOTE_HELPER = "/bin/evac-transfer"
STOP = threading.Event()
CHILDREN = set()
CHILD_LOCK = threading.Lock()
HANDSHAKES = threading.Semaphore(2)


def log(message):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def emit(value):
    print(json.dumps(value), flush=True)


def read_json(path):
    return json.loads(Path(path).read_text())


def atomic_json(path, value, durable=False):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    with temp.open("w") as out:
        json.dump(value, out)
        out.write("\n")
        out.flush()
        if durable:
            os.fsync(out.fileno())
    os.replace(temp, path)
    if durable:
        sync_dir(path.parent)


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def digest_file(path, limit=None):
    digest = hashlib.sha256()
    count = 0
    with Path(path).open("rb") as source:
        while limit is None or count < limit:
            data = source.read(MIB if limit is None else min(MIB, limit - count))
            if not data:
                break
            count += len(data)
            digest.update(data)
    if limit is not None and count != limit:
        raise RuntimeError("Archive is shorter than its durable checkpoint")
    return digest, count


def safe_name(value):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
        raise ValueError("Unsafe archive name")
    return value


def receiver_paths(args):
    base = Path(args.directory)
    name = safe_name(args.namespace) + "--" + safe_name(args.snapshot) + ".tar"
    if args.compression == "lz4":
        name += ".lz4"
    elif args.compression == "zstd":
        name += ".zst"
    final = base / name
    return final, base / (name + ".partial"), base / (name + ".transfer.json"), base / (name + ".json")


def existing_compression(args):
    found = []
    for compression in ("none", "lz4", "zstd"):
        probe = copy.copy(args)
        probe.compression = compression
        if any(p.exists() for p in receiver_paths(probe)):
            found.append(compression)
    if len(found) > 1:
        raise RuntimeError("Multiple archive formats exist for this snapshot")
    return found[0] if found else None


def receive_archive(args):
    """One HDD writer. Each acknowledged block and checkpoint is durable."""
    os.umask(0o077)
    final, partial, checkpoint, receipt = receiver_paths(args)
    final.parent.mkdir(parents=True, exist_ok=True)
    lock = final.with_name(final.name + ".lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    identity = {"namespace": args.namespace, "snapshot": args.snapshot, "compression": args.compression,
                "chunk_size": args.chunk_size}
    if receipt.exists():
        result = read_json(receipt)
        if any(result.get(k) != v for k, v in identity.items()):
            raise RuntimeError("Completed archive identity differs")
        if not final.exists() and partial.exists():
            digest, count = digest_file(partial)
            if count != result["bytes"] or digest.hexdigest() != result["sha256"]:
                raise RuntimeError("Interrupted final rename: archive hash differs")
            os.replace(partial, final)
            sync_dir(final.parent)
        if not final.is_file() or final.stat().st_size != result["bytes"]:
            raise RuntimeError("Completed archive is missing or has changed size")
        emit({"complete": True, **result})
        return
    if final.exists():
        raise RuntimeError("Refusing to overwrite an archive without its receipt")
    state = {**identity, "chunks": 0, "bytes": 0,
             "sha256": hashlib.sha256().hexdigest()}
    if checkpoint.exists():
        state = read_json(checkpoint)
        if any(state.get(k) != v for k, v in identity.items()):
            raise RuntimeError("Partial archive identity differs")
    elif partial.exists():
        raise RuntimeError("Partial archive has no checkpoint")
    if state["bytes"]:
        digest, _ = digest_file(partial, state["bytes"])
        if digest.hexdigest() != state["sha256"]:
            raise RuntimeError("Partial archive checksum differs from checkpoint")
    else:
        digest = hashlib.sha256()
    old_session = state.get("session")
    if old_session:
        old = Path(old_session)
        if old.parent == Path(args.ram_dir) and old.name.startswith("evac-pg-") and old.exists():
            shutil.rmtree(old)
    need_ram = args.chunk_size * (args.lanes + 2)
    if shutil.disk_usage(args.ram_dir).free < need_ram:
        raise RuntimeError("Not enough free space in the receiver RAM buffer")
    session = Path(tempfile.mkdtemp(prefix="evac-pg-", dir=args.ram_dir))
    os.chmod(session, 0o700)
    state["session"] = str(session)
    atomic_json(session / "config.json", {"chunk_size": args.chunk_size, "lanes": args.lanes})
    atomic_json(session / "ack.json", {"chunks": state["chunks"]})
    control = queue.Queue()

    def control_reader():
        try:
            line = sys.stdin.readline()
            control.put(json.loads(line) if line else {"abort": "Sender disconnected"})
        except Exception as error:
            control.put({"abort": str(error)})

    threading.Thread(target=control_reader, daemon=True).start()
    finish = None
    try:
        with partial.open("r+b" if partial.exists() else "w+b") as out:
            out.truncate(state["bytes"])
            out.seek(state["bytes"])
            out.flush()
            os.fsync(out.fileno())
            atomic_json(checkpoint, state, durable=True)
            emit({"ready": True, "session": str(session), **state})
            idle_since = time.monotonic()
            while True:
                (session / "heartbeat").touch()
                try:
                    message = control.get_nowait()
                    if "abort" in message:
                        raise RuntimeError(message["abort"])
                    finish = message
                except queue.Empty:
                    pass
                ready = session / (str(state["chunks"]) + ".ready")
                if ready.exists():
                    with ready.open("rb") as block:
                        header = json.loads(block.readline(4096))
                        if (header["index"] != state["chunks"] or
                                not 0 < header["size"] <= args.chunk_size):
                            raise RuntimeError("Invalid block header")
                        if shutil.disk_usage(final.parent).free < header["size"] + GIB:
                            raise RuntimeError("Destination filesystem has less than 1 GiB reserve")
                        count = 0
                        while data := block.read(MIB):
                            count += len(data)
                            if count > header["size"]:
                                raise RuntimeError("Oversized block")
                            digest.update(data)
                            out.write(data)
                        # The ingress process checked this block before publishing it.
                        # The writer independently hashes the complete archive stream.
                        if count != header["size"]:
                            raise RuntimeError("Block size mismatch")
                    out.flush()
                    os.fsync(out.fileno())
                    state.update(chunks=state["chunks"] + 1, bytes=state["bytes"] + count,
                                 sha256=digest.hexdigest())
                    atomic_json(checkpoint, state, durable=True)
                    ready.unlink()
                    atomic_json(session / "ack.json", {"chunks": state["chunks"]})
                    idle_since = time.monotonic()
                    continue
                if finish is not None:
                    for key in ("chunks", "bytes", "sha256"):
                        if finish.get(key) != state[key]:
                            raise RuntimeError("Final archive " + key + " differs")
                    result = {k: v for k, v in state.items() if k != "session"}
                    result.update(archive=str(final), completed_at=time.time())
                    atomic_json(receipt, result, durable=True)
                    os.replace(partial, final)
                    sync_dir(final.parent)
                    emit({"complete": True, **result})
                    return
                if time.monotonic() - idle_since > 300:
                    raise RuntimeError("No completed block for five minutes")
                time.sleep(0.04)
    finally:
        shutil.rmtree(session)


def receive_block(args):
    """A short SSH session receives one block into RAM, then waits for HDD fsync."""
    os.umask(0o077)
    session = Path(args.session)
    config = read_json(session / "config.json")
    if not 0 < args.size <= config["chunk_size"] or args.index < 0:
        raise RuntimeError("Invalid block bounds")
    ack = read_json(session / "ack.json")["chunks"]
    if args.index < ack:
        emit({"already": True})
        return
    if args.index >= ack + config["lanes"]:
        raise RuntimeError("Block lies outside the bounded receive window")
    ready = session / (str(args.index) + ".ready")
    temp = session / (str(args.index) + ".part." + str(os.getpid()))
    try:
        if ready.exists():
            emit({"already_buffered": True})
        else:
            emit({"ready": True})
            digest = hashlib.sha256()
            remaining = args.size
            with temp.open("xb") as out:
                out.write((json.dumps({"index": args.index, "size": args.size,
                                       "sha256": args.sha256}) + "\n").encode())
                while remaining:
                    data = sys.stdin.buffer.read(min(MIB, remaining))
                    if not data:
                        raise RuntimeError("Truncated incoming block")
                    remaining -= len(data)
                    digest.update(data)
                    out.write(data)
            if digest.hexdigest() != args.sha256:
                raise RuntimeError("Incoming block checksum mismatch")
            os.replace(temp, ready)
        deadline = time.monotonic() + 300
        while read_json(session / "ack.json")["chunks"] <= args.index:
            if time.monotonic() > deadline or time.time() - (session / "heartbeat").stat().st_mtime > 90:
                raise RuntimeError("Archive writer stopped responding")
            time.sleep(0.08)
        emit({"ack": args.index})
    finally:
        if temp.exists():
            temp.unlink()


def spawn(command, **kwargs):
    proc = sp.Popen(command, start_new_session=True, **kwargs)
    with CHILD_LOCK:
        CHILDREN.add(proc)
    return proc


def stop_process(proc):
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
        except ProcessLookupError:
            pass
        except sp.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
    with CHILD_LOCK:
        CHILDREN.discard(proc)
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        if stream is not None and not stream.closed:
            stream.close()


def ssh_command(args, remote):
    return ["ssh", "-F", "/dev/null", "-6", "-T", "-i", str(Path(args.key).expanduser()),
            "-p", "8101", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=" + str(Path(args.known_hosts).expanduser()),
            "-o", "Compression=no", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=20",
            "-o", "ServerAliveCountMax=3", "pg@64:ff9b::5bc:67fb",
            shlex.join(["python3", args.remote_helper, *map(str, remote)])]


def send_block(args, session, index, data):
    digest = hashlib.sha256(data).hexdigest()
    last_error = None
    for attempt in range(3):
        if STOP.is_set():
            raise RuntimeError("Transfer cancelled")
        proc = None
        try:
            with HANDSHAKES:
                proc = spawn(ssh_command(args, ["block", "--session", session, "--index", index,
                                               "--size", len(data), "--sha256", digest]),
                             stdin=sp.PIPE, stdout=sp.PIPE)
                first = json.loads(proc.stdout.readline())
            if first.get("ready"):
                proc.stdin.write(data)
                proc.stdin.close()
                proc.stdin = None
            output, _ = proc.communicate(timeout=310)
            if proc.returncode:
                raise RuntimeError("Block SSH exited " + str(proc.returncode))
            if not first.get("already"):
                final = json.loads(output)
                if final.get("ack") != index:
                    raise RuntimeError("Unexpected block acknowledgment")
            return len(data)
        except Exception as error:
            last_error = error
            log("Block %d attempt %d failed: %s" % (index, attempt + 1, error))
            time.sleep(1 + attempt)
        finally:
            if proc is not None:
                stop_process(proc)
    raise RuntimeError("Block %d failed: %s" % (index, last_error))


def upload(args, namespace, snapshot, source, volume=None):
    if volume is None:
        stats = sp.check_output(ssh_command(args, ["space"]), text=True)
        free = json.loads(stats)
        volume = max(VOLUMES, key=lambda v: free[v])
    directory = "/home/pg/" + volume + "/banners_remote"
    remote = ["receive", "--directory", directory, "--namespace", namespace, "--snapshot", snapshot,
              "--chunk-size", args.chunk_mib * MIB, "--lanes", args.lanes, "--compression", args.compression]
    receiver = spawn(ssh_command(args, remote), stdin=sp.PIPE, stdout=sp.PIPE)
    tar = None
    compressor = None
    started = time.monotonic()
    try:
        status = json.loads(receiver.stdout.readline())
        if status.get("complete"):
            if receiver.wait() != 0:
                raise RuntimeError("Completed-archive check failed")
            return {**status, "volume": volume}
        if not status.get("ready"):
            raise RuntimeError("Receiver failed to initialize")
        tar = spawn(["tar", "--sort=name", "--format=gnu", "--numeric-owner", "-C", str(source.parent),
                     "-cf", "-", source.name], stdout=sp.PIPE)
        stream = tar.stdout
        if args.compression == "lz4":
            compressor = spawn([str(Path(args.lz4).expanduser()), "-1", "-c"], stdin=tar.stdout, stdout=sp.PIPE)
            tar.stdout.close()
            stream = compressor.stdout
        elif args.compression == "zstd":
            compressor = spawn([str(Path(args.zstd).expanduser()), "-1", "-T2", "-c"],
                               stdin=tar.stdout, stdout=sp.PIPE)
            tar.stdout.close()
            stream = compressor.stdout
        digest = hashlib.sha256()
        skipped = 0
        while skipped < status["bytes"]:
            data = stream.read(min(MIB, status["bytes"] - skipped))
            if not data:
                raise RuntimeError("Regenerated tar is shorter than saved prefix")
            digest.update(data)
            skipped += len(data)
        if digest.hexdigest() != status["sha256"]:
            raise RuntimeError("Regenerated tar prefix differs; refusing to resume")
        count, index, acknowledged = skipped, status["chunks"], skipped
        log("Uploading %s to %s; resume=%d bytes, lanes=%d" % (namespace, volume, skipped, args.lanes))
        last_report = time.monotonic()
        last_report_bytes = acknowledged
        with cf.ThreadPoolExecutor(max_workers=args.lanes) as pool:
            pending = set()
            while True:
                if STOP.is_set():
                    raise RuntimeError("Transfer cancelled")
                while len(pending) >= args.lanes:
                    done, pending = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        acknowledged += future.result()
                if time.monotonic() - last_report > 15:
                    seconds = time.monotonic() - last_report
                    log("%s: %.2f GiB durable, recent %.1f Mbit/s" %
                        (namespace, acknowledged / GIB, (acknowledged - last_report_bytes) * 8 / seconds / 1e6))
                    last_report = time.monotonic()
                    last_report_bytes = acknowledged
                data = stream.read(args.chunk_mib * MIB)
                if not data:
                    break
                digest.update(data)
                count += len(data)
                pending.add(pool.submit(send_block, args, status["session"], index, data))
                index += 1
            for future in cf.as_completed(pending):
                acknowledged += future.result()
        if tar.wait() != 0:
            raise RuntimeError("tar reported an error; archive remains partial")
        if compressor is not None and compressor.wait() != 0:
            raise RuntimeError("Compressor reported an error; archive remains partial")
        finish = {"chunks": index, "bytes": count, "sha256": digest.hexdigest()}
        receiver.stdin.write((json.dumps(finish) + "\n").encode())
        receiver.stdin.close()
        receiver.stdin = None
        output, _ = receiver.communicate(timeout=120)
        result = json.loads(output)
        if receiver.returncode or not result.get("complete") or result["sha256"] != finish["sha256"]:
            raise RuntimeError("Archive finalization failed")
        log("Committed %s: %.2f GiB in %.1fs, SHA256=%s" %
            (namespace, count / GIB, time.monotonic() - started, result["sha256"]))
        return {**result, "volume": volume}
    finally:
        if compressor is not None:
            stop_process(compressor)
        if tar is not None:
            stop_process(tar)
        stop_process(receiver)


def yt_environment():
    env = os.environ.copy()
    env["YT_TOKEN"] = (Path.home() / ".yt/token").read_text().strip()
    return env


def download(args, namespace, snapshot, state_dir):
    source = Path(args.staging).expanduser() / namespace
    marker = state_dir / (namespace + ".download.json")
    in_progress = state_dir / (namespace + ".downloading.json")
    identity = {"namespace": namespace, "snapshot": snapshot, "source": str(source)}
    if marker.exists():
        if read_json(marker) != identity or not source.is_dir():
            raise RuntimeError("Download marker disagrees with existing staging directory")
        return source
    if source.exists():
        if in_progress.exists() and read_json(in_progress) == identity:
            shutil.rmtree(source)  # Only an incomplete download created by this pipeline.
        else:
            raise RuntimeError("Unmarked existing download: " + str(source))
    env = yt_environment()
    stat = sp.run(["ya", "tool", "plutonium", "fs", "--yt-proxy", "markov", "--yt-path", YT_FS,
                   "stat-path", "/" + namespace + "/" + snapshot], env=env,
                  stdout=sp.PIPE, stderr=sp.STDOUT, text=True, check=True)
    match = re.search(r"Unique size:\s+([0-9.]+)([KMGT]?i?B)", stat.stdout)
    if not match:
        raise RuntimeError("Cannot estimate download size: " + stat.stdout[-2000:])
    unit = {"B": 1, "KiB": 1024, "MiB": MIB, "GiB": GIB, "TiB": 1024 * GIB}[match[2]]
    required = int(float(match[1]) * unit * 1.2) + args.reserve_gib * GIB
    source.parent.mkdir(parents=True, exist_ok=True)
    if required > shutil.disk_usage(source.parent).total:
        raise RuntimeError("Snapshot cannot fit on source staging filesystem")
    while shutil.disk_usage(source.parent).free < required:
        current_index = int(namespace.rsplit("-", 1)[1])
        reclaim_pending = False
        if not args.keep_source:
            for other_marker in state_dir.glob("*.download.json"):
                try:
                    other = read_json(other_marker)
                    other_index = int(other["namespace"].rsplit("-", 1)[1])
                    if args.start <= other_index < current_index and Path(other["source"]).is_dir():
                        reclaim_pending = True
                except FileNotFoundError:
                    pass  # The uploader finished cleaning that snapshot.
        if not reclaim_pending:
            raise RuntimeError("Insufficient source space for %s: need %.1f GiB including reserve; free %.1f GiB" %
                               (namespace, required / GIB, shutil.disk_usage(source.parent).free / GIB))
        log("Waiting for staging space for " + namespace)
        if STOP.wait(10):
            raise RuntimeError("Download cancelled")
    cmd = ["ya", "tool", "plutonium", "download", "--yt-proxy", "markov", "--yt-worker-path", YT_WORKER,
           "--yt-fs-path", YT_FS, "--namespace", namespace, "--state-id", snapshot, "--out-dir", str(source)]
    log("Downloading " + namespace)
    atomic_json(in_progress, identity, durable=True)
    with (state_dir / (namespace + ".download.log")).open("a") as out:
        proc = spawn(cmd, env=env, stdout=out, stderr=sp.STDOUT)
        try:
            while proc.poll() is None:
                if STOP.wait(1):
                    raise RuntimeError("Download cancelled")
                if shutil.disk_usage(source.parent).free < args.reserve_gib * GIB:
                    raise RuntimeError("Source free space fell below configured reserve")
            if proc.returncode:
                raise RuntimeError("Plutonium download failed; see " + str(out.name))
        finally:
            stop_process(proc)
    atomic_json(marker, identity, durable=True)
    in_progress.unlink()
    log("Download complete: " + namespace)
    return source


def snapshots(args):
    found = {}
    for line in Path(args.snapshots).expanduser().read_text().splitlines():
        match = re.match(r"SnapshotId: ([^,]+), Stream: banners_remote-(\d+),", line)
        if match and args.start <= int(match[2]) <= args.end:
            index = int(match[2])
            if index in found:
                raise RuntimeError("Duplicate snapshot for " + str(index))
            found[index] = safe_name(match[1])
    expected = set(range(args.start, args.end + 1))
    if set(found) != expected:
        raise RuntimeError("Missing snapshots: " + str(sorted(expected - set(found))))
    return found


def run_pipeline(args):
    if not 0 <= args.start <= args.end <= 499:
        raise RuntimeError("Allowed shard range is 0..499 inclusive")
    if not 1 <= args.lanes <= 32 or not 1 <= args.chunk_mib <= 256:
        raise RuntimeError("Invalid transfer bounds")
    if not 1 <= args.uploads <= len(VOLUMES):
        raise RuntimeError("Concurrent archives must be between 1 and 4")
    state_dir = Path(args.state).expanduser()
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = (state_dir / "pipeline.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (state_dir / "pipeline.pid").write_text(str(os.getpid()) + "\n")
    selected = snapshots(args)
    jobs = queue.Queue()
    slots = threading.Semaphore(args.uploads + 1)

    def producer():
        try:
            for index, snapshot in sorted(selected.items()):
                while not slots.acquire(timeout=1):
                    if STOP.is_set():
                        return
                if STOP.is_set():
                    return
                namespace = "banners_remote-" + str(index)
                completed = state_dir / (namespace + ".uploaded.json")
                if completed.exists():
                    result = read_json(completed)
                    if result["snapshot"] != snapshot:
                        raise RuntimeError("Completed snapshot differs from requested snapshot")
                    source = Path(args.staging).expanduser() / namespace
                else:
                    source = download(args, namespace, snapshot, state_dir)
                jobs.put((namespace, snapshot, source))
        except BaseException as error:
            jobs.put(error)
        finally:
            jobs.put(None)

    def upload_and_release(job, volume, compression):
        namespace, snapshot, source = job
        job_args = copy.copy(args)
        job_args.compression = compression
        result = upload(job_args, namespace, snapshot, source, volume)
        atomic_json(state_dir / (namespace + ".uploaded.json"), result, durable=True)
        if not args.keep_source and source.exists():
            marker = state_dir / (namespace + ".download.json")
            identity = read_json(marker)
            if identity != {"namespace": namespace, "snapshot": snapshot, "source": str(source)}:
                raise RuntimeError("Refusing cleanup of an unverified source directory")
            shutil.rmtree(source)
            marker.unlink()
            log("Released verified source staging for " + namespace)
        slots.release()
        return result

    producer_thread = threading.Thread(target=producer, daemon=True)
    pool = cf.ThreadPoolExecutor(max_workers=args.uploads)
    producer_thread.start()
    pending, active = [], {}
    producer_done = False
    log("Pipeline: up to %d archives on separate volumes, %d SSH lanes each" % (args.uploads, args.lanes))
    try:
        while not producer_done or pending or active:
            if STOP.is_set():
                raise RuntimeError("Transfer cancelled")
            for future in list(active):
                if future.done():
                    future.result()
                    del active[future]
            try:
                job = jobs.get(timeout=0.1)
                if job is None:
                    producer_done = True
                elif isinstance(job, BaseException):
                    raise job
                else:
                    pending.append(job)
            except queue.Empty:
                pass
            busy = set(active.values())
            for job in list(pending):
                if len(active) >= args.uploads:
                    break
                namespace, snapshot, source = job
                placement = state_dir / (namespace + ".placement.json")
                if placement.exists():
                    saved = read_json(placement)
                    volume = saved["volume"]
                    if volume not in VOLUMES:
                        raise RuntimeError("Unknown target volume: " + volume)
                    if volume in busy:
                        continue
                    compression = saved.get("compression")
                    if compression is None:
                        completed = state_dir / (namespace + ".uploaded.json")
                        if completed.exists():
                            compression = read_json(completed)["compression"]
                        else:
                            # Upgrade old placement records without changing the
                            # byte stream of an unfinished archive.
                            located = json.loads(sp.check_output(ssh_command(args, [
                                "locate", "--directory", "/home/pg/" + volume + "/banners_remote",
                                "--namespace", namespace, "--snapshot", snapshot]), text=True))
                            compression = located["compression"] or args.compression
                else:
                    # Each partition is an independent target, including both
                    # Seagate partitions. Never run two archives on one target.
                    free = json.loads(sp.check_output(ssh_command(args, ["space"]), text=True))
                    volume = max((v for v in VOLUMES if v not in busy), key=lambda v: free[v])
                    compression = args.compression
                if compression not in ("none", "lz4", "zstd"):
                    raise RuntimeError("Unknown saved compression: " + str(compression))
                atomic_json(placement, {"volume": volume, "compression": compression}, durable=True)
                busy.add(volume)
                pending.remove(job)
                active[pool.submit(upload_and_release, job, volume, compression)] = volume
        log("Completed requested range %d..%d" % (args.start, args.end))
    finally:
        STOP.set()
        with CHILD_LOCK:
            children = list(CHILDREN)
        for proc in children:
            stop_process(proc)
        producer_thread.join(timeout=20)
        pool.shutdown(wait=True, cancel_futures=True)
        pid_file = state_dir / "pipeline.pid"
        if pid_file.exists() and pid_file.read_text().strip() == str(os.getpid()):
            pid_file.unlink()
        lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    receive = commands.add_parser("receive")
    receive.add_argument("--directory", required=True)
    receive.add_argument("--namespace", required=True)
    receive.add_argument("--snapshot", required=True)
    receive.add_argument("--chunk-size", type=int, required=True)
    receive.add_argument("--lanes", type=int, required=True)
    receive.add_argument("--ram-dir", default="/dev/shm")
    receive.add_argument("--compression", choices=("none", "lz4", "zstd"), default="none")
    locate = commands.add_parser("locate")
    locate.add_argument("--directory", required=True)
    locate.add_argument("--namespace", required=True)
    locate.add_argument("--snapshot", required=True)
    block = commands.add_parser("block")
    block.add_argument("--session", required=True)
    block.add_argument("--index", type=int, required=True)
    block.add_argument("--size", type=int, required=True)
    block.add_argument("--sha256", required=True)
    commands.add_parser("space")
    run = commands.add_parser("run")
    run.add_argument("--start", type=int, default=200)
    run.add_argument("--end", type=int, default=249)
    run.add_argument("--snapshots", default="~/pluto.txt")
    run.add_argument("--staging", default="~/banners_remote")
    run.add_argument("--state", default="~/.cache/evac-transfer/pipeline")
    run.add_argument("--key", default="~/qw")
    run.add_argument("--known-hosts", default="~/.cache/evac-access/lab1_known_hosts")
    run.add_argument("--remote-helper", default=REMOTE_HELPER)
    run.add_argument("--uploads", type=int, default=4)
    run.add_argument("--lanes", type=int, default=8)
    run.add_argument("--chunk-mib", type=int, default=64)
    run.add_argument("--reserve-gib", type=int, default=20)
    run.add_argument("--keep-source", action="store_true")
    run.add_argument("--compression", choices=("none", "lz4", "zstd"), default="zstd")
    run.add_argument("--lz4", default="~/.cache/evac-tools/lz4/root/usr/bin/lz4")
    run.add_argument("--zstd", default="zstd")
    args = parser.parse_args()
    if args.command == "receive":
        def receiver_stop(signum, frame):
            raise KeyboardInterrupt("Archive receiver stopped")
        signal.signal(signal.SIGTERM, receiver_stop)
        signal.signal(signal.SIGHUP, receiver_stop)
        receive_archive(args)
    elif args.command == "block":
        receive_block(args)
    elif args.command == "space":
        emit({v: shutil.disk_usage("/home/pg/" + v).free for v in VOLUMES})
    elif args.command == "locate":
        emit({"compression": existing_compression(args)})
    else:
        def stop_signal(signum, frame):
            STOP.set()
            for proc in list(CHILDREN):
                if proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            raise KeyboardInterrupt("Stopped by signal " + str(signum))
        signal.signal(signal.SIGTERM, stop_signal)
        signal.signal(signal.SIGINT, stop_signal)
        run_pipeline(args)


if __name__ == "__main__":
    main()
