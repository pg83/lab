"""
IX keeps some packages as many lines side by side: lib/llvm/21 next to
lib/llvm/20, bin/go/lang/27 next to 26, bin/kernel/7/2 next to 7/1. A line
directory holds one prefix of the upstream version (lib/llvm/21 holds 21.x.y,
bin/go/lang/27 holds 1.27.z) and only ever gets the newest release of that
prefix. A release that opens a prefix past the newest line gets directories
of its own, cloned from the newest line together with everything released
with it (clang, libc++ and compiler-rt come with llvm), and the bin parts of
the new line join CI. Building and fixing them is the fixer's job; defaults
are never moved.

Repology keeps one version per project, so the versions come from the
projects themselves: git tags or a release listing, through the lab's socks
egress.
"""

import re
import shutil
import subprocess
import time
from dataclasses import dataclass


# The line directory first: the version holder of a line is the first of
# these that names a version.
HOLDERS = ('ver.sh', 't/ver.sh', 't/t/ix.sh', 't/ix.sh', 'unwrap/ix.sh', 'impl/ix.sh', 'ix.sh')
VERSION_BLOCK = re.compile(r'\{% block (?:kernel_)?version %\}\s*\n\s*([0-9][^\s{}]*)\s*\n')
CI = 'set/ci/unwrap/linux/x86_64/ix.sh'
# The socks egress restarts its haproxy every few minutes; a listing that
# lands in the restart is asked again past it.
NET_ATTEMPTS = 5
NET_PAUSE = 30


def components(version):
    return re.split(r'[.\-]', version)


def numeric(version):
    return tuple(int(c) if c.isdigit() else -1 for c in components(version))


def everything(version):
    return True


def below(limit):
    """Pre-releases numbered high, as GNU (1.16.92), gperftools (2.15.90) and
    GNOME before a major (3.99.5) do."""
    def stable(version):
        return all(not c.isdigit() or int(c) < limit for c in components(version)[1:])

    return stable


def even(limit=80):
    """GNOME numbering: an odd minor is a development series."""
    under = below(limit)

    def stable(version):
        parts = components(version)
        return under(version) and len(parts) > 1 and parts[1].isdigit() and int(parts[1]) % 2 == 0

    return stable


class NetFailure(OSError):
    pass


class Net:
    def __init__(self, env, attempts=NET_ATTEMPTS, pause=NET_PAUSE, sleep=time.sleep):
        self.proxy = env.get('SOCKS5_PROXY', '')
        self.env = env
        self.attempts = attempts
        self.pause = pause
        self.sleep = sleep

    def run(self, cmd):
        for attempt in range(self.attempts):
            if attempt:
                self.sleep(self.pause)

            try:
                res = subprocess.run(cmd, env=self.env, capture_output=True, timeout=600)
            except subprocess.TimeoutExpired:
                why = 'timed out'
                continue

            if res.returncode == 0:
                return res.stdout.decode(errors='replace')

            tail = res.stderr.decode(errors='replace').strip().splitlines()[-1:]
            why = f'exit {res.returncode}: {" ".join(tail)}'

        raise NetFailure(f'{cmd[-1]}: {why} ({self.attempts} attempts)')

    def tags(self, repo):
        cmd = ['git']

        if self.proxy:
            cmd += ['-c', f'http.proxy=socks5h://{self.proxy}']

        out = self.run(cmd + ['ls-remote', '--tags', '--refs', repo])

        return [l.split('refs/tags/', 1)[1] for l in out.splitlines() if 'refs/tags/' in l]

    def get(self, url):
        cmd = ['curl', '-sSfL', '-m', '300']

        if self.proxy:
            cmd += ['--socks5-hostname', self.proxy]

        return self.run(cmd + [url])


@dataclass(frozen=True)
class Tags:
    repo: str
    pattern: str

    def versions(self, net):
        rx = re.compile(self.pattern)

        return [m.group(1).replace('_', '.') for t in net.tags(self.repo) if (m := rx.fullmatch(t))]


@dataclass(frozen=True)
class Listing:
    url: str
    pattern: str

    def versions(self, net):
        return re.findall(self.pattern, net.get(self.url))


def path_rx(template, args):
    return re.compile(r'(?<![\w.\-])' + re.escape(template.format(*args)) + r'(?![0-9])')


def single(old, new):
    """A family keyed by one number names it alone too: a block holding just
    the major (llvm_major, clang_major_version) and flags like crt_ver=21."""
    def retarget(text):
        text = re.sub(rf'(?m)^(\s*){old[0]}(\s*)$', rf'\g<1>{new[0]}\g<2>', text)

        return re.sub(rf'(_ver=){old[0]}(?![0-9])', rf'\g<1>{new[0]}', text)

    return retarget


def bootstrap(line):
    """go: the new toolchain bootstraps from the line it was cloned from."""
    def factory(old, new):
        def retarget(text):
            return re.sub(
                r'(\{% block go_bootstrap %\}\s*\n)\s*\S+\s*\n',
                lambda m: m.group(1) + line.format(*old) + '\n',
                text,
            )

        return retarget

    return factory


def kernel_tree(old, new):
    def retarget(text):
        return text.replace(f'/v{old[0]}.x/', f'/v{new[0]}.x/')

    return retarget


@dataclass(frozen=True)
class Family:
    name: str
    line: str                 # a line directory, {0}.. are its numbers
    key: str                  # the version prefix a line holds, same numbers
    source: object = None     # None: hands off, nothing here touches the family
    group: tuple = ()         # more directories released with a line
    ci: tuple = ()            # bin parts for CI when the previous line had none there
    url: str = ''             # the version inside a fetch URL or git branch, for lines without a version block
    needs: tuple = ()         # what a new line needs to exist already
    adopt: tuple = ()         # directories of another family's line that move to the new line
    stable: object = everything
    retarget: object = None   # (old numbers, new numbers) -> edit of the cloned files

    @property
    def width(self):
        return len(self.key.split('.'))

    def patterns(self):
        return (self.line, *self.group)

    def rx(self, template):
        parts = re.split(r'\{(\d+)\}', template)
        out = ''

        for i, part in enumerate(parts):
            out += re.escape(part) if i % 2 == 0 else r'(\d+)'

        return re.compile(out)

    def owns(self, package):
        for template in self.patterns():
            m = self.rx(template).match(package)

            if m and (m.end() == len(package) or package[m.end()] == '/'):
                return True

        return False

    def key_of(self, version):
        parts = components(version)

        if len(parts) < self.width:
            return None

        return '.'.join(parts[:self.width])

    def args_of(self, key):
        m = self.rx(self.key).fullmatch(key)

        return m.groups() if m else None

    def lines(self, pkgs):
        """(numbers, directory) of every line in the tree."""
        rx = self.rx(self.line)
        depth = self.line.count('/')
        base = pkgs / self.line.split('{', 1)[0]
        found = []

        if not base.is_dir():
            return found

        for ix in base.rglob('ix.sh'):
            rel = ix.parent.relative_to(pkgs).as_posix()

            if rel.count('/') == depth and (m := rx.fullmatch(rel)):
                found.append((m.groups(), rel))

        return sorted(found, key=lambda x: tuple(int(a) for a in x[0]))

    def holder(self, pkgs, directory):
        """(file, version, literal) a line keeps its version in: a version
        block, or for a line without one the version inside its fetch URL."""
        for literal in (False, True):
            if literal and not self.url:
                break

            for name in HOLDERS:
                path = pkgs / directory / name

                if not path.is_file():
                    continue

                text = path.read_text()
                m = re.search(self.url, text) if literal else VERSION_BLOCK.search(text)

                if m:
                    return f'{directory}/{name}', m.group(1), literal

        return None, None, False


def F(*args, **kw):
    return Family(*args, **kw)


GH = 'https://github.com/'
GNOME = 'https://gitlab.gnome.org/GNOME/'
SAVANNAH = 'https://git.savannah.gnu.org/git/'
LLVM = (
    'bin/clang/{0}', 'lib/c++/{0}', 'lib/compiler_rt/builtins/{0}',
    'lib/compiler_rt/sanitize/address/{0}', 'lib/omp/{0}', 'lib/clc/{0}',
    'lib/mesa/intel/clc/{0}', 'bin/lld/{0}',
)

FAMILIES = (
    F('llvm', 'lib/llvm/{0}', '{0}', Tags(GH + 'llvm/llvm-project', r'llvmorg-(\d+\.\d+\.\d+)'),
      group=LLVM, ci=('bin/clang/{0}',), url=r'llvmorg-(\d+\.\d+\.\d+)', retarget=single),
    F('spirv-llvm-translator', 'lib/spirv/llvm/translator/{0}', '{0}',
      Tags(GH + 'KhronosGroup/SPIRV-LLVM-Translator', r'v(\d+\.\d+\.\d+)'),
      group=('bin/llvm/spirv/{0}',), ci=('bin/llvm/spirv/{0}',), needs=('lib/llvm/{0}',),
      adopt=('lib/clc/{0}', 'lib/mesa/intel/clc/{0}')),
    F('gcc', 'bin/gcc/{0}', '{0}', Tags(GH + 'gcc-mirror/gcc', r'releases/gcc-(\d+\.\d+\.\d+)'), ci=('bin/gcc/{0}',)),
    F('go', 'bin/go/lang/{0}', '1.{0}', Tags(GH + 'golang/go', r'go(1\.\d+\.\d+)'),
      ci=('bin/go/lang/{0}',), retarget=bootstrap('bin/go/lang/{0}')),
    F('python', 'lib/python/3/{0}', '3.{0}', Tags(GH + 'python/cpython', r'v(3\.\d+\.\d+)'),
      group=('bin/python/{0}', 'bld/python/{0}'), ci=('bin/python/{0}',)),
    F('lua', 'lib/lua/puc/5/{0}', '5.{0}', Listing('https://www.lua.org/ftp/', r'lua-(5\.\d+\.\d+)\.tar\.gz')),
    F('kernel', 'bin/kernel/{0}/{1}', '{0}.{1}',
      Tags('https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git', r'v(\d+\.\d+(?:\.\d+)?)'),
      ci=('bin/kernel/{0}/{1}',), retarget=kernel_tree),
    F('wlroots', 'lib/wlroots/{0}', '0.{0}', Tags('https://gitlab.freedesktop.org/wlroots/wlroots.git', r'(0\.\d+\.\d+)')),
    F('fmt', 'lib/fmt/{0}', '{0}', Tags(GH + 'fmtlib/fmt', r'(\d+\.\d+\.\d+)')),
    F('nlohmann-json', 'lib/json/nlohmann/{0}', '3.{0}', Tags(GH + 'nlohmann/json', r'v(3\.\d+\.\d+)')),
    F('gperftools', 'lib/gperftools/{0}', '2.{0}',
      Tags(GH + 'gperftools/gperftools', r'gperftools-(2\.\d+(?:\.\d+)?)'), stable=below(80)),
    F('ffmpeg', 'lib/ffmpeg/{0}', '{0}', Tags(GH + 'FFmpeg/FFmpeg', r'n(\d+\.\d+(?:\.\d+)?)'),
      url=r'/n(\d+\.\d+(?:\.\d+)?)\.tar'),
    F('boost', 'lib/boost/{0}', '1.{0}', Tags(GH + 'boostorg/boost', r'boost-(1\.\d+\.\d+)'),
      url=r'boost-(1\.\d+\.\d+)/'),
    F('placebo', 'lib/placebo/{0}', '{0}', Tags('https://code.videolan.org/videolan/libplacebo.git', r'v(\d+\.\d+\.\d+)')),
    F('mimalloc', 'lib/mimalloc/{0}', '{0}', Tags(GH + 'microsoft/mimalloc', r'v(\d+\.\d+\.\d+)')),
    F('cairomm', 'lib/cairo/mm/{0}', '1.{0}', Tags('https://gitlab.freedesktop.org/cairo/cairomm.git', r'(1\.\d+\.\d+)'),
      stable=even()),
    F('openssl', 'lib/openssl/{0}', '{0}', Tags(GH + 'openssl/openssl', r'openssl-(\d+\.\d+\.\d+)')),
    F('mbedtls', 'lib/mbedtls/{0}', '{0}', Tags(GH + 'Mbed-TLS/mbedtls', r'(?:v|mbedtls-)(\d+\.\d+\.\d+)')),
    F('fuse', 'lib/fuse/{0}', '{0}', Tags(GH + 'libfuse/libfuse', r'fuse-(\d+\.\d+\.\d+)'),
      group=('bin/fusermount/{0}',), ci=('bin/fusermount/{0}',)),
    F('sdl', 'lib/sdl/{0}', '{0}', Tags(GH + 'libsdl-org/SDL', r'release-(\d+\.\d+\.\d+)'), stable=even()),
    F('gtk', 'lib/gtk/{0}', '{0}', Tags(GNOME + 'gtk.git', r'(\d+\.\d+\.\d+)'), stable=even()),
    F('gtksourceview', 'lib/gtk/source/view/{0}', '{0}', Tags(GNOME + 'gtksourceview.git', r'(\d+\.\d+\.\d+)'),
      stable=even()),
    F('sigc++', 'lib/sigc++/{0}', '{0}', Tags(GH + 'libsigcplusplus/libsigcplusplus', r'(\d+\.\d+\.\d+)'),
      stable=even()),
    F('libsoup', 'lib/soup/{0}', '{0}', Tags(GNOME + 'libsoup.git', r'(\d+\.\d+\.\d+)'), stable=even()),
    F('srtp', 'lib/srtp/{0}', '{0}', Tags(GH + 'cisco/libsrtp', r'v(\d+\.\d+\.\d+)')),
    F('gcr', 'lib/gcr/{0}', '{0}', Tags(GNOME + 'gcr.git', r'(\d+\.\d+\.\d+)'), stable=below(90),
      group=('bin/gcr/viewer/{0}',), ci=('bin/gcr/viewer/{0}',)),
    F('fcft', 'lib/fcft/{0}', '{0}', Tags('https://codeberg.org/dnkl/fcft.git', r'(\d+\.\d+\.\d+)')),
    F('glaze', 'lib/glaze/{0}', '{0}', Tags(GH + 'stephenberry/glaze', r'v(\d+\.\d+\.\d+)')),
    F('meson', 'bin/meson/1/{0}', '1.{0}', Tags(GH + 'mesonbuild/meson', r'(1\.\d+\.\d+)'), ci=('bin/meson/1/{0}',)),
    F('autoconf', 'bin/auto/conf/2/{0}', '2.{0}', Tags(SAVANNAH + 'autoconf.git', r'v(2\.\d+)'),
      ci=('bin/auto/conf/2/{0}',)),
    F('automake', 'bin/auto/make/1/{0}', '1.{0}', Tags(SAVANNAH + 'automake.git', r'v(1\.\d+(?:\.\d+)?)'),
      stable=below(80)),
    F('bison', 'bin/bison/3/{0}', '3.{0}', Tags(SAVANNAH + 'bison.git', r'v(3\.\d+(?:\.\d+)?)'), stable=below(80)),
    F('coreutils', 'bin/coreutils/{0}/{1}', '{0}.{1}', Tags(SAVANNAH + 'coreutils.git', r'v(\d+\.\d+)'),
      ci=('bin/coreutils/{0}/{1}',)),
    F('bash', 'bin/bash/{0}', '{0}', Listing('https://ftp.gnu.org/gnu/bash/', r'bash-(\d+\.\d+(?:\.\d+)?)\.tar\.gz"')),
    F('dropbear', 'bin/dropbear/{0}', '{0}', Tags(GH + 'mkj/dropbear', r'DROPBEAR_(\d{4}\.\d+)'),
      ci=('bin/dropbear/{0}',)),
    F('postgresql', 'bin/postgresql/{0}', '{0}', Tags(GH + 'postgres/postgres', r'REL_?(\d+_\d+)'),
      ci=('bin/postgresql/{0}',)),
    F('mariadb', 'bin/mariadb/{0}', '{0}', Tags(GH + 'MariaDB/server', r'mariadb-(\d+\.\d+\.\d+)'),
      ci=('bin/mariadb/{0}',), url=r'mariadb-(\d+\.\d+\.\d+)'),
    F('gdb', 'bin/gdb/{0}', '{0}', Tags('https://sourceware.org/git/binutils-gdb.git', r'gdb-(\d+\.\d+)-release'),
      ci=('bin/gdb/{0}',)),
    F('qemu8', 'bin/qemu/8/{0}', '8.{0}', Tags(GH + 'qemu/qemu', r'v(8\.\d+\.\d+)'), url=r'\bv(8\.\d+\.\d+)\b'),
    # Numbered, but not lines this code keeps: exact pins, consumer-bound
    # versions, different projects under one name, bootstrap stages.
    F('automake-1.16', 'bin/auto/make/1/16/{0}', '1.16.{0}'),
    F('m4', 'bin/m4/{0}', '1.4.{0}'),
    F('esbuild', 'bin/esbuild/{0}', '0.{0}'),
    F('gost', 'bin/gost/{0}', '{0}'),
    F('ragel', 'bin/ragel/{0}', '{0}'),
)


def owned(packages, families=FAMILIES):
    return any(f.owns(p) for f in families for p in packages)


def newest(versions, key, family, above):
    pool = [v for v in versions if family.key_of(v) == key and numeric(v) > numeric(above)]

    return max(pool, key=numeric) if pool else None


def retarget_paths(text, family, old, new):
    for template in family.patterns():
        text = path_rx(template, old).sub(template.format(*new), text)

    if family.width > 1:
        # A dotted key names the line by itself: python3.14, libpython3.14.a,
        # boost_1_87; a full version (3.14.8) is the version holder's.
        for sep in ('.', '_'):
            was = sep.join(family.key.format(*old).split('.'))
            now = sep.join(family.key.format(*new).split('.'))
            before = r'(?<![\d.])' if sep == '.' else r'(?<!\d)'
            text = re.sub(before + re.escape(was) + rf'(?![0-9])(?!\{sep}[0-9])', now, text)

    if family.retarget:
        text = family.retarget(old, new)(text)

    return text


def adopt(pkgs, family, old, new):
    """A new line of this family takes over what another family's line of
    the same number referred to: lib/clc/22, cloned with llvm 22 while only
    the translator 21 was there, gets translator 22."""
    moved = []

    for template in family.adopt:
        directory = pkgs / template.format(*new)

        if not directory.is_dir():
            continue

        for f in directory.rglob('*.sh'):
            text = f.read_text()
            changed = text

            for pattern in family.patterns():
                changed = path_rx(pattern, old).sub(pattern.format(*new), changed)

            if changed != text:
                f.write_text(changed)
                moved.append(f.relative_to(pkgs).as_posix())

    return moved


def clone(pkgs, family, old, new):
    """Copy every directory of line old to line new; the paths inside, and
    whatever the family names its line by, follow."""
    made = []

    for template in family.patterns():
        src = pkgs / template.format(*old)
        dst = pkgs / template.format(*new)

        if not src.is_dir() or dst.exists():
            continue

        shutil.copytree(src, dst)
        made.append(template.format(*new))

        # Recipes include sources of any kind (plan.py, gl3_sdl.c): all text follows.
        for f in dst.rglob('*'):
            if not f.is_file():
                continue

            try:
                text = f.read_text()
            except UnicodeDecodeError:
                continue

            f.write_text(retarget_paths(text, family, old, new))

    return made


def add_to_ci(pkgs, family, old, new):
    """Whatever CI builds of line old, it builds of line new; when it built
    nothing, the family's bin parts."""
    path = pkgs / CI
    text = path.read_text()
    rows = text.split('\n')
    have = {r.strip() for r in rows}
    olds = [re.compile(r'\s*' + re.escape(t.format(*old)) + r'(?![0-9])') for t in family.patterns()]
    out = []
    added = []

    for row in rows:
        out.append(row)
        s = row.strip()

        if s and not s.startswith('#') and any(rx.match(s) for rx in olds):
            entry = retarget_paths(s, family, old, new)

            if entry not in have and entry not in added:
                out.append(row[:len(row) - len(row.lstrip())] + entry)
                added.append(entry)

    if not added:
        end = max(i for i, r in enumerate(out) if r.strip() == '{% endblock %}')

        for template in family.ci:
            entry = template.format(*new)

            if entry not in have:
                out.insert(end, entry)
                end += 1
                added.append(entry)

    path.write_text('\n'.join(out))

    return added


class Lines:
    def __init__(self, updater, net, log, failure, families=FAMILIES):
        self.updater = updater
        self.net = net
        self.log = log
        self.failure = failure
        self.families = families
        self.pkgs = updater.repo / 'pkgs'

    def run(self):
        done = 0
        failed = 0

        for family in self.families:
            if family.source is None:
                continue

            try:
                versions = [v for v in set(family.source.versions(self.net)) if family.stable(v)]
            except (OSError, subprocess.SubprocessError) as exc:
                self.log(f'FAILED {family.name}: cannot list versions: {exc}')
                failed += 1
                continue

            d, f = self.family(family, versions)
            done += d
            failed += f

        self.log(f'lines done: updated={done} failed={failed}')

    def family(self, family, versions):
        done = failed = 0
        lines = family.lines(self.pkgs)

        for args, directory in lines:
            holder, ours, literal = family.holder(self.pkgs, directory)
            key = family.key.format(*args)

            if not holder:
                self.log(f'skip {directory}: no version found')
                continue

            if family.key_of(ours) != key:
                self.log(f'skip {directory}: holds {ours}, outside {key}')
                continue

            target = newest(versions, key, family, ours)

            if not target:
                continue

            try:
                self.updater.bump(holder, ours, target, [directory], literal)
                self.updater.publish(f'up {ours} {target} {directory}')
                done += 1
            except self.failure as exc:
                self.log(f'FAILED {directory} {ours} -> {target}: {exc}')
                failed += 1
            finally:
                self.updater.restore()

        if not lines:
            return done, failed

        top = max(numeric(family.key.format(*a)) for a, _ in lines)
        keys = sorted({k for v in versions if (k := family.key_of(v)) and family.args_of(k) and numeric(k) > top},
                      key=numeric)

        # One new line a run: the next one clones from it, after it is published.
        if keys:
            try:
                if self.new_line(family, lines[-1], keys[0], versions):
                    done += 1
            except self.failure as exc:
                self.log(f'FAILED {family.name} {keys[0]}: new line: {exc}')
                failed += 1
            finally:
                self.updater.restore()

        return done, failed

    def new_line(self, family, last, key, versions):
        old, directory = last
        new = family.args_of(key)

        for need in family.needs:
            if not (self.pkgs / need.format(*new)).is_dir():
                self.log(f'skip {family.name} {key}: no {need.format(*new)} yet')
                return False

        target = max((v for v in versions if family.key_of(v) == key), key=numeric)
        made = clone(self.pkgs, family, old, new)

        if not made:
            return False

        holder, ours, literal = family.holder(self.pkgs, family.line.format(*new))

        if not holder:
            raise self.failure(f'no version in {family.line.format(*new)}')

        self.updater.bump(holder, ours, target, [family.line.format(*new)], literal)
        made += adopt(self.pkgs, family, old, new)
        ci = add_to_ci(self.pkgs, family, old, new)
        self.updater.render(made)
        # What CI builds, the way it builds it.
        self.updater.render(['set/ci'], ('--seed=1',))
        self.updater.publish(f'{family.name} {key}: new line {target} ({", ".join(made)}); CI: {", ".join(ci) or "-"}')
        self.log(f'new line {family.name} {key}: {", ".join(made)}')

        return True
