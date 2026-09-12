# ZIP artifacts

Single-file Python service: `lab/artifacts.py`. Runs on all three lab hosts.
MinIO bucket `view`, object key = lowercase SHA-256 of the exact ZIP bytes,
computed by the upload server. No listing, mutable aliases, or deletion API.

## Publish

Put `index.html` at the ZIP root; use relative asset URLs. Upload from mesh:

```sh
cd site
zip -r ../site.zip .
curl --fail-with-body -H 'X-Artifact-Upload: 1' \
  --data-binary @../site.zip http://192.168.100.16:8055/api/artifacts
```

Response: `{"sha256":"…","url":"https://view.homelab.cam/view/…/"}`.
Repeat uploads of identical bytes have identical URLs. ZIP metadata is part
of the hash; independently repacked ZIPs need not have the same hash.

## Read

`GET /view/<sha>/` serves `index.html`; nested paths read individual ZIP
members without extraction. `/view/<sha>` redirects to its trailing-slash
form so relative links work. Direct mesh reads work on port 8055 too.
Port 8056 listens only on loopback and is the Cloudflare tunnel origin.
Only `/view/.*` is routed publicly; the upload API is not exposed.

Successful immutable responses use `Cache-Control: public,
max-age=315360000, immutable` (ten years), including HTML. Errors use
`no-store`. Cloudflare cache eligibility must explicitly include HTML:
match `view.homelab.cam` and `/view/`, set cache eligibility on and respect
origin TTL. An edge cache can evict entries before TTL; MinIO is permanent
storage. Never replace different bytes at an existing hash or purge on upload.

Cloudflare zone `05a072b3cb835aced0e3745559d27640`, cache ruleset
`a20e5738a893401c9fce2370307fe58e`, rule `dd787192453d40abbe5c717855730e07`
(`ref=view_zip_cas`). The rule enables caching with `edge_ttl` and
`browser_ttl` set to `respect_origin`; it does not cache `no-store` errors.
DNS is a proxied CNAME to tunnel `4b335fae-9cd1-40bb-9868-08deb4a23cb7`.

Artifacts run under CSP sandbox without `allow-same-origin`: JavaScript works,
but cookies, localStorage, service workers and access to other artifacts are
intentionally unavailable. CORS allows static module/font loading. External
resources are not bundled automatically. Sites must not rely on a backend.

Limits: 64 MiB ZIP, 32 MiB/member, 256 MiB unpacked, 4096 entries. Only stored
and deflated ZIPs; paths, CRCs, duplicates and file types are validated before
publication. No extraction, symlinks, encrypted archives or directory listing.
Each replica caches at most eight ZIPs in its process-owned temporary directory.

Tests: `python3 -m unittest discover -s tst -p test_artifacts.py`.
