#!/usr/bin/env python3
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import view


class MonitorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.roots = {v: self.root / v for v in view.VOLUMES}
        for root in self.roots.values():
            (root / "banners_remote").mkdir(parents=True)
        real_stat = Path.stat
        roots = set(self.roots.values())

        def fake_mount_stat(path, *args, **kwargs):
            stat = real_stat(path, *args, **kwargs)
            if path in roots:
                fields = list(stat)
                fields[2] += 1
                return os.stat_result(fields)
            return stat

        self.mount_patch = patch.object(Path, "stat", fake_mount_stat)
        self.mount_patch.start()
        self.addCleanup(self.mount_patch.stop)

    def archive(self, complete=False, size=128):
        folder = self.roots["hgst-a"] / "banners_remote"
        archive = "banners_remote-200--snapshot.tar.zst"
        data = {"namespace": "banners_remote-200", "bytes": 128, "sha256": "a" * 64,
                "compression": "zstd", "session": "/private/secret"}
        (folder / (archive + ("" if complete else ".partial"))).write_bytes(b"x" * size)
        (folder / (archive + (".json" if complete else ".transfer.json"))).write_text(json.dumps(data))
        return folder, archive

    def test_receipt_required_and_no_double_count_at_completion(self):
        folder, archive = self.archive()
        records, _, issues = view.scan_volumes(self.roots)
        self.assertFalse(issues)
        self.assertFalse(records[200]["complete"])
        (folder / (archive + ".partial")).replace(folder / archive)
        records, _, issues = view.scan_volumes(self.roots)
        self.assertNotIn(200, records)  # rename alone is not a confirmed receipt
        self.archive(complete=True)
        records, _, issues = view.scan_volumes(self.roots)
        self.assertFalse(issues)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[200]["bytes"], 128)
        self.assertTrue(records[200]["complete"])
        self.assertNotIn("session", records[200])

    def test_receipt_wrong_size_and_truncated_checkpoint_are_not_complete(self):
        self.archive(complete=True, size=127)
        records, _, issues = view.scan_volumes(self.roots)
        self.assertFalse(records)
        self.assertTrue(issues)
        self.archive(complete=False, size=127)
        records, _, issues = view.scan_volumes(self.roots)
        self.assertFalse(records)
        self.assertTrue(issues)

    def test_unmounted_directory_cannot_be_reported_as_free_destination(self):
        self.mount_patch.stop()
        records, volumes, issues = view.scan_volumes(self.roots)
        self.assertFalse(records)
        self.assertTrue(all(not v["available"] for v in volumes))
        self.assertEqual(len(issues), 4)

    def test_rates_restart_staleness_and_public_whitelist(self):
        monitor = view.Monitor()
        status = {"checked_at": 1000, "connected": True, "plan": {"private": "secret"},
                  "error": "secret", "tail": ["private token"],
                  "service": {"ActiveState": "active", "SubState": "running", "MainPID": 1}}
        records = {200: {"bytes": 100, "complete": False, "updated_at": 1000}}
        volumes = [{"name": n, "available": True, "free_bytes": 100 * 1024**3} for n in view.VOLUMES]
        source = {"available": True, "checked_at": 1000, "free_bytes": 30 * 1024**3,
                  "ready": [201], "downloading": [202], "private": "secret"}
        first = monitor.snapshot(status, records, volumes, source, [], 1000)
        self.assertIsNone(first["summary"]["mbps"])
        self.assertEqual(first["shards"][1]["phase"], "ready")
        self.assertEqual(first["shards"][2]["phase"], "downloading")
        records[200]["bytes"] += 50_000_000
        second = monitor.snapshot(status, records, volumes, source, [], 1005)
        self.assertEqual(second["summary"]["mbps"], 80)
        self.assertNotIn("secret", json.dumps(second))
        self.assertNotIn("private token", json.dumps(second))
        records[200]["complete"] = True
        records[200]["sha256"] = "a" * 64
        third = monitor.snapshot(status, records, volumes, source, [], 1010)
        self.assertEqual(third["summary"]["completed"], 1)
        self.assertEqual(third["summary"]["bytes"], 50_000_100)
        records[200]["bytes"] = 10
        reset = monitor.snapshot(status, records, volumes, source, [], 1015)
        self.assertIsNone(reset["summary"]["mbps"])
        stale = monitor.snapshot(status, records, volumes, source, [], 1200)
        self.assertFalse(stale["connected"])
        self.assertFalse(stale["source"]["available"])
        self.assertEqual(stale["shards"][1]["phase"], "waiting")

    def test_http_serves_only_explicit_public_routes(self):
        public = self.root / "public.json"
        public.write_text('{"ok":true}')
        assets = Path(__file__).parent
        server = view.ThreadingHTTPServer(("127.0.0.1", 0), view.handler(public, assets))
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_port
        for route in ("/", "/app.js", "/style.css", "/api/status"):
            with urlopen(base + route) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        for route in ("/../../public.json", "/source-id", "/api/stop"):
            with self.assertRaises(HTTPError) as error:
                urlopen(base + route)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(base + "/api/status", data=b"{}", method="POST"))
        self.assertEqual(error.exception.code, 501)
        error.exception.close()


if __name__ == "__main__":
    unittest.main()
