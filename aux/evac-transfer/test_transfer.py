import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name("transfer.py")


class ReceiverTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.processes = []

    def tearDown(self):
        for proc in self.processes:
            if proc.poll() is None:
                proc.kill()
            proc.communicate()
        self.temp.cleanup()

    def start(self):
        proc = subprocess.Popen([sys.executable, str(SCRIPT), "receive", "--directory", str(self.root / "data"),
                                 "--namespace", "banners_remote-200", "--snapshot", "snapshot1",
                                 "--chunk-size", "4096", "--lanes", "4", "--ram-dir", str(self.root)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.processes.append(proc)
        first = proc.stdout.readline()
        if not first:
            raise RuntimeError(proc.stderr.read().decode())
        return proc, json.loads(first)

    def block(self, status, index, data, bad_hash=False):
        digest = "0" * 64 if bad_hash else hashlib.sha256(data).hexdigest()
        return subprocess.run([sys.executable, str(SCRIPT), "block", "--session", status["session"],
                               "--index", str(index), "--size", str(len(data)), "--sha256", digest],
                              input=data, capture_output=True, timeout=15)

    def finish(self, proc, blocks):
        content = b"".join(blocks)
        finish = {"chunks": len(blocks), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        output, errors = proc.communicate((json.dumps(finish) + "\n").encode(), timeout=15)
        self.assertEqual(proc.returncode, 0, errors.decode())
        result = json.loads(output)
        self.assertEqual(Path(result["archive"]).read_bytes(), content)
        return result

    def test_out_of_order_blocks_and_already_complete(self):
        proc, status = self.start()
        blocks = [b"a" * 4096, b"b" * 4096, b"tail"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(self.block, status, i, blocks[i]) for i in [2, 0, 1]]
            for future in futures:
                result = future.result()
                self.assertEqual(result.returncode, 0, result.stderr.decode())
        receipt = self.finish(proc, blocks)
        again, status = self.start()
        self.assertTrue(status["complete"])
        self.assertEqual(status["sha256"], receipt["sha256"])
        self.assertEqual(again.wait(timeout=5), 0)

    def test_resume_truncates_uncommitted_tail(self):
        proc, status = self.start()
        blocks = [b"first" * 700, b"second" * 100]
        result = self.block(status, 0, blocks[0])
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        proc.communicate(timeout=10)  # EOF cancels; durable prefix must remain.
        self.assertNotEqual(proc.returncode, 0)
        partial = next((self.root / "data").glob("*.partial"))
        with partial.open("ab") as out:
            out.write(b"uncommitted garbage")
        resumed, status = self.start()
        self.assertEqual(status["chunks"], 1)
        self.assertEqual(status["bytes"], len(blocks[0]))
        self.assertEqual(partial.stat().st_size, len(blocks[0]))
        duplicate = self.block(status, 0, blocks[0])
        self.assertEqual(duplicate.returncode, 0)
        self.assertTrue(json.loads(duplicate.stdout)["already"])
        result = self.block(status, 1, blocks[1])
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.finish(resumed, blocks)

    def test_corrupt_block_is_rejected_without_advancing_checkpoint(self):
        proc, status = self.start()
        result = self.block(status, 0, b"bad data", bad_hash=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads((Path(status["session"]) / "ack.json").read_text())["chunks"], 0)
        good = self.block(status, 0, b"good data")
        self.assertEqual(good.returncode, 0, good.stderr.decode())
        self.finish(proc, [b"good data"])

    def test_corrupt_durable_prefix_is_rejected(self):
        proc, status = self.start()
        self.assertEqual(self.block(status, 0, b"known bytes").returncode, 0)
        proc.communicate(timeout=10)
        partial = next((self.root / "data").glob("*.partial"))
        partial.write_bytes(b"wrong bytes")
        with self.assertRaisesRegex(RuntimeError, "checksum differs"):
            self.start()


class SenderTest(unittest.TestCase):
    def test_streaming_tar_resume_preserves_hardlinks(self):
        spec = importlib.util.spec_from_file_location("evac_transfer", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "banners_remote-200"
            source.mkdir()
            (source / "a.bin").write_bytes(os.urandom(5 * 1024 ** 2))
            os.link(source / "a.bin", source / "b.bin")
            (source / "empty").mkdir()
            (source / "link").symlink_to("a.bin")
            reference = subprocess.check_output(["tar", "--sort=name", "--format=gnu", "--numeric-owner",
                                                 "-C", str(root), "-cf", "-", source.name])
            dest = root / "destination"
            dest.mkdir()
            name = "banners_remote-200--snapshot1.tar"
            prefix = reference[:1024 ** 2]
            (dest / (name + ".partial")).write_bytes(prefix)
            module.atomic_json(dest / (name + ".transfer.json"), {
                "namespace": source.name, "snapshot": "snapshot1", "compression": "none",
                "chunk_size": 1024 ** 2, "chunks": 1, "bytes": len(prefix),
                "sha256": hashlib.sha256(prefix).hexdigest()})
            args = types.SimpleNamespace(lanes=4, chunk_mib=1, compression="none")

            def local_command(args, remote):
                remote = list(map(str, remote))
                if remote[0] == "receive":
                    remote[remote.index("--directory") + 1] = str(dest)
                    remote += ["--ram-dir", str(root)]
                return [sys.executable, str(SCRIPT), *remote]

            with mock.patch.object(module, "ssh_command", side_effect=local_command):
                result = module.upload(args, source.name, "snapshot1", source, "hgst-a")
            self.assertEqual(Path(result["archive"]).read_bytes(), reference)
            self.assertLess(len(reference), 6 * 1024 ** 2)  # Hardlink payload was stored once.
            self.assertEqual(result["sha256"], hashlib.sha256(reference).hexdigest())

    def test_download_overlaps_upload_with_only_one_snapshot_ahead(self):
        spec = importlib.util.spec_from_file_location("evac_pipeline", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            selected = root / "snapshots.txt"
            selected.write_text("".join("SnapshotId: snapshot%d, Stream: banners_remote-%d, Status: Active\n" %
                                        (i, i) for i in range(200, 203)))
            args = types.SimpleNamespace(start=200, end=202, lanes=4, chunk_mib=1,
                                         state=str(root / "state"), staging=str(root / "staging"),
                                         snapshots=str(selected), keep_source=True, compression="none", uploads=1)
            uploading = threading.Event()
            prefetched = threading.Event()
            third_started = threading.Event()
            order = []

            def fake_download(args, namespace, snapshot, state):
                if namespace.endswith("201"):
                    if not uploading.wait(5):
                        raise RuntimeError("Downloader did not overlap uploader")
                    prefetched.set()
                if namespace.endswith("202"):
                    third_started.set()
                path = Path(args.staging) / namespace
                path.mkdir(parents=True)
                return path

            def fake_upload(args, namespace, snapshot, source, volume):
                if namespace.endswith("200"):
                    uploading.set()
                    self.assertTrue(prefetched.wait(5))
                    self.assertFalse(third_started.is_set())
                order.append(namespace)
                return {"namespace": namespace, "snapshot": snapshot, "compression": "none"}

            with mock.patch.object(module, "download", side_effect=fake_download), \
                 mock.patch.object(module, "upload", side_effect=fake_upload), \
                 mock.patch.object(module, "ssh_command", return_value=["space"]), \
                 mock.patch.object(module.sp, "check_output", return_value=json.dumps({v: 100 for v in module.VOLUMES})):
                module.run_pipeline(args)
            self.assertEqual(order, ["banners_remote-200", "banners_remote-201", "banners_remote-202"])

    def test_four_archives_use_distinct_volumes_and_resume_existing_placement(self):
        spec = importlib.util.spec_from_file_location("evac_parallel", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / "state"
            state.mkdir()
            selected = root / "snapshots.txt"
            selected.write_text("".join("SnapshotId: s%d, Stream: banners_remote-%d, Status: Active\n" % (i, i)
                                        for i in range(200, 206)))
            # Two pre-existing placements must never write this target together.
            module.atomic_json(state / "banners_remote-200.placement.json", {"volume": "seagate-b"})
            module.atomic_json(state / "banners_remote-200.uploaded.json", {"snapshot": "s200", "compression": "lz4"})
            module.atomic_json(state / "banners_remote-204.placement.json",
                               {"volume": "seagate-b", "compression": "none"})
            args = types.SimpleNamespace(start=200, end=205, uploads=4, lanes=2, chunk_mib=1,
                                         state=str(state), staging=str(root / "staging"), snapshots=str(selected),
                                         keep_source=True, compression="zstd")
            lock = threading.Lock()
            first_four = threading.Barrier(4, timeout=8)
            prefetched = threading.Event()
            active, assignments, downloaded = set(), {}, []

            def fake_download(args, namespace, snapshot, state):
                with lock:
                    downloaded.append(namespace)
                if namespace.endswith("204"):
                    prefetched.set()
                path = Path(args.staging) / namespace
                path.mkdir(parents=True)
                return path

            def fake_upload(args, namespace, snapshot, source, volume):
                expected = {"banners_remote-200": "lz4", "banners_remote-204": "none"}.get(namespace, "zstd")
                self.assertEqual(args.compression, expected)
                with lock:
                    self.assertNotIn(volume, active)
                    active.add(volume)
                    assignments[namespace] = volume
                if int(namespace.rsplit("-", 1)[1]) < 204:
                    first_four.wait()
                    self.assertTrue(prefetched.wait(5))
                    with lock:
                        self.assertNotIn("banners_remote-205", downloaded)
                    first_four.wait()
                with lock:
                    active.remove(volume)
                return {"namespace": namespace, "snapshot": snapshot, "compression": "none", "volume": volume}

            with mock.patch.object(module, "download", side_effect=fake_download), \
                 mock.patch.object(module, "upload", side_effect=fake_upload), \
                 mock.patch.object(module, "ssh_command", return_value=["space"]), \
                 mock.patch.object(module.sp, "check_output", return_value=json.dumps({v: 100 for v in module.VOLUMES})):
                module.run_pipeline(args)
            self.assertEqual(set(assignments["banners_remote-%d" % i] for i in range(200, 204)), set(module.VOLUMES))
            self.assertEqual(assignments["banners_remote-204"], "seagate-b")
            self.assertEqual(len(assignments), 6)
            self.assertFalse((state / "pipeline.pid").exists())

    @unittest.skipUnless(shutil.which("zstd"), "zstd executable is required")
    def test_zstd_resume_regenerates_identical_compressed_stream(self):
        spec = importlib.util.spec_from_file_location("evac_zstd", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "banners_remote-201"
            source.mkdir()
            (source / "data").write_bytes(os.urandom(3 * 1024 ** 2) + b"repeating" * 200000)
            os.link(source / "data", source / "hardlink")
            tar = subprocess.check_output(["tar", "--sort=name", "--format=gnu", "--numeric-owner",
                                           "-C", str(root), "-cf", "-", source.name])
            reference = subprocess.check_output(["zstd", "-1", "-T2", "-c"], input=tar)
            dest = root / "dest"
            dest.mkdir()
            prefix = reference[:1024 ** 2]
            name = "banners_remote-201--s201.tar.zst"
            (dest / (name + ".partial")).write_bytes(prefix)
            module.atomic_json(dest / (name + ".transfer.json"), {
                "namespace": source.name, "snapshot": "s201", "compression": "zstd",
                "chunk_size": 1024 ** 2, "chunks": 1, "bytes": len(prefix),
                "sha256": hashlib.sha256(prefix).hexdigest()})
            args = types.SimpleNamespace(lanes=4, chunk_mib=1, compression="zstd", zstd="zstd")

            def local_command(args, remote):
                remote = list(map(str, remote))
                if remote[0] == "receive":
                    remote[remote.index("--directory") + 1] = str(dest)
                    remote += ["--ram-dir", str(root)]
                return [sys.executable, str(SCRIPT), *remote]

            with mock.patch.object(module, "ssh_command", side_effect=local_command):
                result = module.upload(args, source.name, "s201", source, "hgst-a")
            self.assertEqual(Path(result["archive"]).read_bytes(), reference)
            self.assertEqual(subprocess.check_output(["zstd", "-dc", result["archive"]]), tar)
            probe = types.SimpleNamespace(directory=str(dest), namespace=source.name, snapshot="s201")
            self.assertEqual(module.existing_compression(probe), "zstd")


class ServiceTest(unittest.TestCase):
    def test_reconcile_after_controller_restart_does_not_restart_worker(self):
        import base64
        spec = importlib.util.spec_from_file_location("evac_source_agent", SCRIPT.with_name("source_agent.py"))
        agent = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent)
        payload = {"worker_b64": base64.b64encode(SCRIPT.read_bytes()).decode(),
                   "plan": {"enabled": True, "start": 200, "end": 249, "uploads": 4, "lanes": 8, "chunk_mib": 64}}
        with tempfile.TemporaryDirectory() as temp, \
             mock.patch.object(agent.subprocess, "run") as run, \
             mock.patch.object(agent.subprocess, "check_output", return_value="ActiveState=active\nSubState=running\n"):
            agent.reconcile(payload, temp)
            self.assertTrue(any("restart" in c.args[0] for c in run.call_args_list))
            run.reset_mock()
            agent.reconcile(payload, temp)
            self.assertFalse(any("restart" in c.args[0] or "daemon-reload" in c.args[0] for c in run.call_args_list))
            payload["plan"]["uploads"] = 2
            agent.reconcile(payload, temp)
            self.assertTrue(any("restart" in c.args[0] for c in run.call_args_list))
            run.reset_mock()
            payload["plan"]["enabled"] = False
            agent.reconcile(payload, temp)
            self.assertTrue(any("disable" in c.args[0] and "--now" in c.args[0] for c in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
