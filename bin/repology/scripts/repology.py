#!/usr/bin/env python3

"""
Our repology: upstream repology-updater code, run as job_scheduler jobs
with s3 instead of PostgreSQL.

    repology fetch <repo>   fetch and parse one repository, upload the
                            parsed package chunks to
                            repology/parsed/<code commit>/<repo>.tar.zst
    repology aggregate      download every repository's chunks, classify
                            versions across them and write
                            repology/projects.json — the projects that
                            contain a stalix package, in the shape of
                            the upstream API — plus projects.meta.json

The code is a clone of the ogorod mirror of repology-updater at a pinned
commit; rules and repos.d come from the mirror of repology-rules and the
same clone at master, live. The pinned code is patched in place at start
(see patch()) and completed by stand-in modules from share/repology/shims
for libversion, xxhash, yarl, jsonslicer and pydantic, so no wheel beyond
PyYAML and jinja2 is needed.

Runs in a fresh gorn tmpfs: the working directory is the state. S3 goes
through minio-client with the MC_HOST_minio alias; the egress socks proxy
is REPOLOGY_SOCKS5.
"""

import datetime
import json
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


OGOROD = os.environ.get('REPOLOGY_OGOROD', 'http://127.0.0.1:8035')
SHARE = Path(os.environ.get('REPOLOGY_SHARE', '/ix/realm/system/share/repology'))
BUCKET = 'minio/repology'

# repology-updater commit the jobs run; bump together with patch() below.
UPDATER_COMMIT = '254f53ccfcbfb32509f0fe9f7ab0c86a81816000'

# Repositories the aggregate compares stalix against. Names as in repos.d.
REPOS = (
    'alpine_edge',
    'arch',
    'debian_unstable',
    'fedora_rawhide',
    'freebsd',
    'gnuguix',
    'homebrew',
    'macports',
    'nix_unstable',
    'opensuse_tumbleweed',
    'stalix',
    'stalix_dev',
    'void_x86_64',
)

OURS = ('stalix', 'stalix_dev')


def log(*args):
    print('+', *args, file=sys.stderr, flush=True)


def run(*args, **kwargs):
    log(*args)

    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def replace_once(path, old, new):
    text = path.read_text()

    if text.count(old) != 1:
        raise SystemExit(f'patch anchor not found exactly once in {path}: {old!r}')

    path.write_text(text.replace(old, new))


def patch(updater):
    # HTTP over curl through the socks proxy; brotli and zstd as binaries.
    shutil.copy(SHARE / 'overlay' / 'http.py', updater / 'repology' / 'fetchers' / 'http.py')

    # The class factory imports every parser and fetcher module; the ones
    # for repositories we do not run need wheels we do not ship.
    moduleutils = updater / 'repology' / 'moduleutils.py'
    replace_once(moduleutils, 'import inspect\n', 'import inspect\nimport sys\n')
    replace_once(
        moduleutils,
        '            submodule = importlib.import_module(submodulename)\n',
        '            try:\n'
        '                submodule = importlib.import_module(submodulename)\n'
        '            except ImportError as e:\n'
        '                print(f"skipping {submodulename}: {e}", file=sys.stderr)\n'
        '                continue\n',
    )

    # GNU tar picks the decompressor by magic; -z breaks void's zstd repodata.
    # gorn runs us as root of a user namespace: tar would chown to the
    # archive's uids, which are not mapped there (arch: uid 1055).
    replace_once(
        updater / 'repology' / 'fetchers' / 'fetchers' / 'tar.py',
        "['tar', '-x', '-z', '-f', tarpath",
        "['tar', '-x', '--no-same-owner', '-f', tarpath",
    )


def checkout(work):
    updater = work / 'updater'
    rules = work / 'rules'

    run('git', 'clone', '-q', f'{OGOROD}/mirror_repology-updater.git', updater)
    run('git', '-C', updater, 'checkout', '-q', UPDATER_COMMIT)
    run('git', 'clone', '-q', '--depth', '1', f'{OGOROD}/mirror_repology-rules.git', rules)

    rules_commit = subprocess.check_output(['git', '-C', rules, 'rev-parse', 'HEAD'], text=True).strip()

    patch(updater)

    sys.path[:0] = [str(SHARE / 'shims'), str(updater)]

    return updater, rules, rules_commit


def mc(*args):
    return run('minio-client', *args, stdout=subprocess.DEVNULL)


def put(local, key):
    mc('cp', '--disable-multipart', local, f'{BUCKET}/{key}')


def get(key, local):
    mc('cp', f'{BUCKET}/{key}', local)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def chunk_counts(parsed_dir):
    # Every chunk starts with a pickled package count.
    total = 0

    for chunk in parsed_dir.iterdir():
        with open(chunk, 'rb') as f:
            total += pickle.Unpickler(f).load()

    return total


def repomgr_and_proc(work, updater):
    from repology.repomgr import RepositoryManager
    from repology.repoproc import RepositoryProcessor
    from repology.yamlloader import YamlConfig

    repomgr = RepositoryManager(YamlConfig.from_path(str(updater / 'repos.d')))
    repoproc = RepositoryProcessor(repomgr, str(work / '_state'), str(work / '_parsed'))

    return repomgr, repoproc


def fetch(repo):
    work = Path.cwd()
    updater, rules, rules_commit = checkout(work)

    from repology.logger import StderrLogger
    from repology.transformer import PackageTransformer
    from repology.transformer.ruleset import Ruleset
    from repology.yamlloader import YamlConfig

    repomgr, repoproc = repomgr_and_proc(work, updater)
    repository = repomgr.get_repository(repo)
    logger = StderrLogger()

    repoproc.fetch([repo], update=True, logger=logger)

    ruleset = Ruleset(YamlConfig.from_path(str(rules)))
    transformer = PackageTransformer(ruleset, repo, repository.ruleset)
    repoproc.parse([repo], transformer=transformer, maintainermgr=None, logger=logger)

    parsed = work / '_parsed' / f'{repo}.parsed'
    archive = work / f'{repo}.tar.zst'
    run('tar', '--zstd', '-c', '-f', archive, '-C', work / '_parsed', parsed.name)

    meta = {
        'repo': repo,
        'code': UPDATER_COMMIT,
        'rules': rules_commit,
        'packages': chunk_counts(parsed),
        'fetched': now(),
    }
    meta_path = work / f'{repo}.json'
    meta_path.write_text(json.dumps(meta, indent=4, sort_keys=True) + '\n')

    put(archive, f'parsed/{UPDATER_COMMIT}/{repo}.tar.zst')
    put(meta_path, f'parsed/{UPDATER_COMMIT}/{repo}.json')

    log(f'{repo}: {meta["packages"]} packages')


def record(package, status):
    # The upstream API record; fields absent from the package are left out.
    fields = {
        'repo': package.repo,
        'subrepo': package.subrepo,
        'srcname': package.srcname,
        'binname': package.binname,
        'binnames': package.binnames,
        'visiblename': package.visiblename,
        'version': package.version,
        'origversion': package.origversion,
        'status': status,
        'summary': package.comment,
        'categories': [package.category] if package.category else None,
        'licenses': package.licenses,
        'maintainers': package.maintainers,
    }

    return {k: v for k, v in fields.items() if v is not None}


def select(packageset, ours=OURS):
    """True for a project the aggregate publishes: one with a package of ours."""
    return any(package.repo in ours for package in packageset)


def aggregate():
    work = Path.cwd()
    updater, rules, rules_commit = checkout(work)

    from repology.classifier import classify_packages
    from repology.logger import StderrLogger
    from repology.package import PackageStatus

    parsed_dir = work / '_parsed'
    parsed_dir.mkdir()
    metas = {}

    for repo in REPOS:
        archive = work / f'{repo}.tar.zst'
        meta_path = work / f'{repo}.json'

        try:
            get(f'parsed/{UPDATER_COMMIT}/{repo}.json', meta_path)
            get(f'parsed/{UPDATER_COMMIT}/{repo}.tar.zst', archive)
        except subprocess.CalledProcessError:
            log(f'{repo}: no parsed data for code {UPDATER_COMMIT}, skipping')
            continue

        run('tar', '--zstd', '-x', '-f', archive, '-C', parsed_dir)
        archive.unlink()
        metas[repo] = json.loads(meta_path.read_text())

    if not metas:
        raise SystemExit('nothing parsed yet')

    repomgr, repoproc = repomgr_and_proc(work, updater)
    projects = {}
    total = 0

    for packageset in repoproc.iter_parsed(reponames=list(metas), logger=StderrLogger()):
        total += 1

        if not select(packageset):
            continue

        classify_packages(packageset)
        projects[packageset[0].effname] = [
            record(package, PackageStatus.as_string(package.versionclass))
            for package in packageset
        ]

    meta = {
        'code': UPDATER_COMMIT,
        'rules': rules_commit,
        'generated': now(),
        'projects_total': total,
        'projects': len(projects),
        'repos': metas,
    }

    projects_path = work / 'projects.json'
    meta_path = work / 'projects.meta.json'
    projects_path.write_text(json.dumps(projects, sort_keys=True, separators=(',', ':')) + '\n')
    meta_path.write_text(json.dumps(meta, indent=4, sort_keys=True) + '\n')

    put(projects_path, 'projects.json')
    put(meta_path, 'projects.meta.json')

    log(f'{len(projects)} of {total} projects written')


def main():
    tempfile.tempdir = os.getcwd()

    match sys.argv[1:]:
        case ['fetch', repo]:
            fetch(repo)
        case ['aggregate']:
            aggregate()
        case _:
            raise SystemExit('usage: repology fetch <repo> | repology aggregate')


if __name__ == '__main__':
    main()
