#!/usr/bin/env python3

"""
tail/log — in-memory log-tail fallback. Shells out to `tail -F` for
the list of paths passed on argv, parses the `==> path <==` headers
it prints between files, and keeps the last 50k lines in a deque for
HTTP readback. Intended as a loki-independent way to see what
happened on each host when loki's ring is split.

Argv:
    1. bind host (nebula IP)
    2. listen port
    3..N. paths to tail -F

Storage: collections.deque(maxlen=50000). Auto-drops oldest append
on overflow, O(1).

HTTP API (GET /):
    ?n=N         last N records (default 100, applied last)
    ?path=<re>   regex filter on path (re.search semantics)
    ?q=<re>      regex filter on line body
    ?since=<ts>  drop records with ts < given unix float

Response: one JSON object per line ({"path":..., "ts":float, "line":str}),
with a trailing newline. `Content-Type: application/jsonl`.

tail -F handles rotation (tinylog renames current → _<ts>.s and
opens a fresh current), truncation, and missing-at-start files by
itself — we just parse its output.
"""

import os
import re
import sys
import json
import time
import threading
import subprocess
import collections

import http.server as hs
import urllib.parse as up


BUF_SIZE = 50_000

HEADER_RE = re.compile(r'^==> (.+) <==$')


buf = collections.deque(maxlen=BUF_SIZE)
buf_lock = threading.Lock()


def reader(paths):
    # -F follow-by-name; -v forces headers; busybox tail rejects --.
    proc = subprocess.Popen(
        ['tail', '-F', '-v', '-n', '0'] + paths,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=1,
        text=True,
    )

    current = paths[0] if paths else ''

    for line in proc.stdout:
        line = line.rstrip('\n')

        m = HEADER_RE.match(line)

        if m:
            current = m.group(1)
            continue

        if not line:
            continue

        with buf_lock:
            buf.append({'path': current, 'ts': time.time(), 'line': line})


def filter_items(items, q):
    path_re = re.compile(q['path'][0]) if 'path' in q else None
    line_re = re.compile(q['q'][0]) if 'q' in q else None
    since = float(q['since'][0]) if 'since' in q else None

    for rec in items:
        if since is not None and rec['ts'] < since:
            continue

        if path_re and not path_re.search(rec['path']):
            continue

        if line_re and not line_re.search(rec['line']):
            continue

        yield rec


class Handler(hs.BaseHTTPRequestHandler):
    def do_GET(self):
        q = up.parse_qs(up.urlparse(self.path).query)
        n = int(q.get('n', ['100'])[0])

        with buf_lock:
            snapshot = list(buf)

        out = list(filter_items(snapshot, q))[-n:]

        body = ('\n'.join(json.dumps(r) for r in out) + '\n').encode()

        self.send_response(200)
        self.send_header('Content-type', 'application/jsonl')
        self.send_header('Content-length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    host = sys.argv[1]
    port = int(sys.argv[2])
    paths = sys.argv[3:]

    threading.Thread(target=reader, args=(paths,), daemon=True).start()

    hs.ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == '__main__':
    main()
