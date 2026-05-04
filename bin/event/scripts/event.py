#!/usr/bin/env python3

"""
event — pub-sub on etcd_1.

Subcommands:

  event http
      HTTP server on $EVENT_HTTP_PORT. POST /api/v1/schedule with
      body {"kind": "<kind>", "payload": {...}} → fresh GUID,
      etcdctl put /event/queue/<guid> = {kind, guid, payload},
      returns {"guid": "..."}. Runs on every host so schedule
      always sees a local listener.

  event dispatch
      Drains /event/queue/* under (caller-held) etcdctl lock
      /lock/event/dispatch — singleton via the lock, runit
      restarts on lock loss. For each entry, walks
      /etc/event/<kind>/**/*.json recursively, parses
      {"cmd": [...]}, expands $VAR/${VAR} in each arg from the
      dispatcher's env, exec's the result with json.dumps({kind,
      guid, payload}) on stdin. Subscribers that need creds
      pin them explicitly: /bin/env A=$A B=$B prog. Failed
      subscribers go to /event/dlq/<dlq-guid>; the queue entry
      is deleted only after every subscriber has either
      succeeded or been DLQ'd.

  event retry
      Drains /event/dlq/* under /lock/event/retry. Re-runs each
      entry's recorded cmd; on success deletes, on failure bumps
      attempts in place. No max attempts, no backoff — sleep 10s
      between sweeps.

  event schedule <kind>
      CLI. stdin = payload (json or empty), POST to
      127.0.0.1:$EVENT_HTTP_PORT/api/v1/schedule, retries infra
      failures (connection refused, timeout, 5xx) until 200. 4xx
      aborts loudly.

Wire format in etcd:
  /event/queue/<guid> → {"kind": "...", "guid": "...", "payload": {...}}
  /event/dlq/<dlq-guid> → {kind, guid, payload, script_path, cmd, attempts, last_rc, last_output}
"""

import base64
import glob
import http.client
import http.server as hs
import json
import os
import subprocess
import sys
import time
import uuid


EVENTS_DIR = '/etc/event'
QUEUE_PREFIX = '/event/queue/'
DLQ_PREFIX = '/event/dlq/'
DISPATCH_INTERVAL_S = 1
RETRY_INTERVAL_S = 10
SCHEDULE_RETRY_INTERVAL_S = 2
OUTPUT_TAIL = 2048


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def etcdctl(*args, input=None):
    return subprocess.run(
        ('etcdctl',) + args,
        input=input,
        stdout=subprocess.PIPE,
        check=True,
    ).stdout


def list_prefix(prefix):
    raw = etcdctl('get', '--prefix', '-w', 'json', prefix)
    d = json.loads(raw)
    out = []

    for kv in d.get('kvs') or ():
        key = base64.b64decode(kv['key']).decode()
        val = base64.b64decode(kv['value']).decode()
        out.append((key, val))

    return out


def put(key, val):
    etcdctl('put', key, val)


def delete(key):
    etcdctl('del', key)


def is_safe_kind(kind):
    if not isinstance(kind, str) or not kind or kind.startswith('/'):
        return False

    parts = kind.split('/')

    return all(p and p != '..' and p != '.' for p in parts)


def walk_subscribers(kind):
    base = os.path.join(EVENTS_DIR, kind)

    if not os.path.isdir(base):
        return []

    return sorted(glob.glob(os.path.join(base, '**', '*.json'), recursive=True))


def load_subscriber(js):
    with open(js) as f:
        cfg = json.load(f)

    cmd = cfg['cmd']

    if not isinstance(cmd, list) or not cmd:
        raise ValueError(f'{js}: cmd must be a non-empty list')

    return cmd


def expand(cmd):
    return [os.path.expandvars(a) for a in cmd]


def run_subscriber(cmd, req):
    return subprocess.run(
        expand(cmd),
        input=json.dumps(req),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


def enqueue_dlq(req, script_path, cmd, rc, output):
    dlq_guid = uuid.uuid4().hex
    rec = {
        'kind': req['kind'],
        'guid': req['guid'],
        'payload': req['payload'],
        'script_path': script_path,
        'cmd': cmd,
        'attempts': 1,
        'last_rc': rc,
        'last_output': (output or '')[-OUTPUT_TAIL:],
    }
    put(f'{DLQ_PREFIX}{dlq_guid}', json.dumps(rec))
    log(f'dlq enqueued {dlq_guid} script={script_path}')


def dispatch_one(key, value):
    try:
        req = json.loads(value)
    except Exception as e:
        log(f'dispatch: bad json at {key}: {e}; deleting')
        delete(key)
        return

    kind = req.get('kind')

    if not is_safe_kind(kind):
        log(f'dispatch: bad kind={kind!r} at {key}; deleting')
        delete(key)
        return

    log(f'dispatch guid={req.get("guid")} kind={kind}')

    subs = walk_subscribers(kind)

    if not subs:
        log(f'  no subscribers under {EVENTS_DIR}/{kind}/')

    for js in subs:
        try:
            cmd = load_subscriber(js)
        except Exception as e:
            log(f'  subscriber {js}: load failed: {e}; queuing to DLQ')
            enqueue_dlq(req, js, [], -1, str(e))
            continue

        log(f'  -> {js} cmd={cmd}')
        res = run_subscriber(cmd, req)

        if res.returncode == 0:
            log(f'  ok')
        else:
            log(f'  failed rc={res.returncode}; queuing to DLQ')
            enqueue_dlq(req, js, cmd, res.returncode, res.stdout or '')

    delete(key)


def cmd_dispatch():
    log('event dispatch: starting')

    while True:
        try:
            entries = list_prefix(QUEUE_PREFIX)
        except subprocess.CalledProcessError as e:
            log(f'dispatch: list failed: {e}; sleeping')
            time.sleep(DISPATCH_INTERVAL_S)
            continue

        for key, val in entries:
            try:
                dispatch_one(key, val)
            except subprocess.CalledProcessError as e:
                log(f'dispatch: etcd op failed for {key}: {e}; will retry next round')

        time.sleep(DISPATCH_INTERVAL_S)


def retry_one(key, value):
    try:
        rec = json.loads(value)
    except Exception as e:
        log(f'retry: bad json at {key}: {e}; deleting')
        delete(key)
        return

    cmd = rec.get('cmd')

    if not cmd:
        log(f'retry: no cmd in {key}; deleting')
        delete(key)
        return

    req = {'kind': rec['kind'], 'guid': rec['guid'], 'payload': rec['payload']}
    attempt = rec.get('attempts', 0) + 1
    log(f'retry {key} attempt={attempt} script={rec.get("script_path")}')

    res = run_subscriber(cmd, req)

    if res.returncode == 0:
        log(f'  ok; deleting {key}')
        delete(key)
        return

    rec['attempts'] = attempt
    rec['last_rc'] = res.returncode
    rec['last_output'] = (res.stdout or '')[-OUTPUT_TAIL:]
    put(key, json.dumps(rec))
    log(f'  failed rc={res.returncode}; attempts={attempt}')


def cmd_retry():
    log('event retry: starting')

    while True:
        try:
            entries = list_prefix(DLQ_PREFIX)
        except subprocess.CalledProcessError as e:
            log(f'retry: list failed: {e}; sleeping')
            time.sleep(RETRY_INTERVAL_S)
            continue

        for key, val in entries:
            try:
                retry_one(key, val)
            except subprocess.CalledProcessError as e:
                log(f'retry: etcd op failed for {key}: {e}')

        time.sleep(RETRY_INTERVAL_S)


class HTTPHandler(hs.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/api/v1/schedule':
            self.send_error(404, 'unknown endpoint')
            return

        n = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(n) if n else b''

        try:
            req = json.loads(body or b'{}')
        except Exception as e:
            self.send_error(400, f'bad json: {e}')
            return

        kind = req.get('kind')

        if not is_safe_kind(kind):
            self.send_error(400, f'bad kind: {kind!r}')
            return

        payload = req.get('payload', {})
        guid = uuid.uuid4().hex
        rec = {'kind': kind, 'guid': guid, 'payload': payload}

        try:
            put(f'{QUEUE_PREFIX}{guid}', json.dumps(rec))
        except subprocess.CalledProcessError as e:
            self.send_error(500, f'etcd put failed: {e}')
            return

        out = json.dumps({'guid': guid}).encode() + b'\n'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, fmt, *args):
        sys.stderr.write(
            f'{self.client_address[0]} - [{self.log_date_time_string()}] {fmt % args}\n'
        )


def cmd_http():
    port = int(os.environ['EVENT_HTTP_PORT'])
    log(f'event http: listening on 127.0.0.1:{port}')
    hs.ThreadingHTTPServer(('127.0.0.1', port), HTTPHandler).serve_forever()


def cmd_schedule(kind):
    if not is_safe_kind(kind):
        print(f'event schedule: bad kind {kind!r}', file=sys.stderr)
        sys.exit(2)

    raw = sys.stdin.read()

    if raw.strip():
        try:
            payload = json.loads(raw)
        except Exception as e:
            print(f'event schedule: stdin not valid json: {e}', file=sys.stderr)
            sys.exit(2)
    else:
        payload = {}

    body = json.dumps({'kind': kind, 'payload': payload}).encode()
    port = int(os.environ.get('EVENT_HTTP_PORT', '8053'))

    while True:
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=10)

        try:
            conn.request(
                'POST', '/api/v1/schedule',
                body=body,
                headers={'Content-Type': 'application/json'},
            )
            resp = conn.getresponse()
            data = resp.read()
        except (ConnectionRefusedError, http.client.HTTPException, OSError) as e:
            log(f'event schedule: infra error: {e}; retrying in {SCHEDULE_RETRY_INTERVAL_S}s')
            conn.close()
            time.sleep(SCHEDULE_RETRY_INTERVAL_S)
            continue

        conn.close()

        if resp.status == 200:
            sys.stdout.write(data.decode())
            return

        if 400 <= resp.status < 500:
            print(f'event schedule: {resp.status} from API: {data.decode()}', file=sys.stderr)
            sys.exit(1)

        log(f'event schedule: {resp.status} from API; retrying')
        time.sleep(SCHEDULE_RETRY_INTERVAL_S)


def main():
    if len(sys.argv) < 2:
        print('usage: event {http|dispatch|retry|schedule <kind>}', file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]

    if cmd == 'http':
        cmd_http()
    elif cmd == 'dispatch':
        cmd_dispatch()
    elif cmd == 'retry':
        cmd_retry()
    elif cmd == 'schedule':
        if len(sys.argv) != 3:
            print('usage: event schedule <kind>', file=sys.stderr)
            sys.exit(2)
        cmd_schedule(sys.argv[2])
    else:
        print(f'unknown subcommand: {cmd}', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
