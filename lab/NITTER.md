# Nitter

`Nitter` in `cg.py` runs on lab1, lab2 and lab3 as uid 2016. It listens on
`127.0.0.1:8063`; the existing Cloudflare tunnel publishes it at
`https://nitter.homelab.cam`. Its DNS record points to
`4b335fae-9cd1-40bb-9868-08deb4a23cb7.cfargotunnel.com`.

Each instance uses `http://127.0.0.1:8061` (`kv front`). The `nitter` bucket
has a 1 GiB byte limit on each `kv back`, for 3 GiB across the cluster.
Expiry is encoded in Nitter's cache records. KV does not replicate data;
restarting a backend empties that backend's cache.

The shared signing key is `/nitter/hmac` in the encrypted secrets store.
Account sessions belong in `/nitter/sessions`, as JSONL in Nitter's format.
The service supplies configuration and sessions through inherited memory file
descriptors, without writing plaintext credentials to the package store.
An empty sessions value permits the site to start but cannot fetch posts from X.
After changing sessions, restart Nitter to load them into its session pool.

For account-session creation, see `tools/create_session_browser.py` in the
Nitter repository. Sessions are account credentials and belong only in the
encrypted secrets store. `enableDebug` stays disabled on the public instance.

Changes deploy through the usual lab commit/push and host autoupdate. Package
compilation runs on the lab hosts. The Nitter package recipe is mirrored from
`ix/pkgs/bin/nitter/pg83` into the lab overlay.

Check `http://127.0.0.1:8063/` and `/css/style.css` on each host, then the public
domain. KV exposes `kv_bucket_capacity_bytes{bucket="nitter"}` on localhost
port 8062; it should report 1073741824 on every host.
