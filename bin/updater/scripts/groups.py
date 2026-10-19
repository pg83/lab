"""
Some packages of IX are released together under one version: the Qt modules
(qtbase, qtdeclarative, ... at 6.12.0) and the Vulkan SDK (Vulkan-Headers,
Vulkan-Loader, SPIRV-Tools, ... at vulkan-sdk-1.4.363.0). Moved one by one
they come apart, so a group moves as a whole: to the newest release every
member of it has tagged, every member below it in one commit. The checksums
are probed in one build that keeps going past failed fetches. Nothing is
built beyond the probes; CI and the fixer take it from there.
"""

import re
from dataclasses import dataclass

from lines import VERSION_BLOCK, numeric


@dataclass(frozen=True)
class Member:
    directory: str        # the package a probe builds
    holder: str           # the file keeping its version
    repo: str             # where the release tags are
    tag: str              # a release tag, {} is the version
    literal: bool = False  # the version is inside a fetch URL, not a version block

    def version_in(self, text):
        if self.literal:
            m = re.search(re.escape(self.tag).replace(r'\{\}', r'(\d[\w.\-]*?)') + r'(?=\.tar|\.zip|/|$)', text)
        else:
            m = VERSION_BLOCK.search(text)

        return m.group(1) if m else None

    def owns(self, package):
        return package == self.directory or package.startswith(self.directory + '/')


@dataclass(frozen=True)
class Group:
    name: str
    version: str          # a release version, a regex
    members: tuple

    def releases(self, tags, member):
        rx = re.compile(re.escape(member.tag).replace(r'\{\}', f'({self.version})'))

        return {m.group(1) for t in tags if (m := rx.fullmatch(t))}


GH = 'https://github.com/'
KHRONOS = GH + 'KhronosGroup/'


def qt(directory, holder, module):
    return Member(directory, holder, f'{GH}qt/{module}', 'v{}')


def sdk(directory, holder, repo, literal=False):
    return Member(directory, holder, repo, 'vulkan-sdk-{}', literal)


GROUPS = (
    Group('qt', r'6\.\d+\.\d+', (
        qt('lib/qt/6/base', 'lib/qt/6/base/t/ix.sh', 'qtbase'),
        qt('lib/qt/6/charts', 'lib/qt/6/charts/ix.sh', 'qtcharts'),
        qt('lib/qt/6/compat', 'lib/qt/6/compat/ix.sh', 'qt5compat'),
        qt('lib/qt/6/declarative', 'lib/qt/6/declarative/t/ix.sh', 'qtdeclarative'),
        qt('lib/qt/6/imageformats', 'lib/qt/6/imageformats/ix.sh', 'qtimageformats'),
        qt('lib/qt/6/multimedia', 'lib/qt/6/multimedia/t/ix.sh', 'qtmultimedia'),
        qt('lib/qt/6/shadertools', 'lib/qt/6/shadertools/t/ix.sh', 'qtshadertools'),
        qt('lib/qt/6/svg', 'lib/qt/6/svg/ix.sh', 'qtsvg'),
        qt('lib/qt/6/wayland', 'lib/qt/6/wayland/t/ix.sh', 'qtwayland'),
        qt('bld/qt/6/tools', 'bld/qt/6/tools/ix.sh', 'qttools'),
    )),
    # glslang keeps its own numbering and the repology updater; shaderc and
    # MoltenVK are released on their own.
    Group('vulkan-sdk', r'\d+\.\d+\.\d+\.\d+', (
        sdk('lib/vulkan/headers', 'lib/vulkan/headers/ix.sh', KHRONOS + 'Vulkan-Headers'),
        sdk('lib/vulkan/loader', 'lib/vulkan/loader/t/ix.sh', KHRONOS + 'Vulkan-Loader'),
        sdk('lib/vulkan/utility', 'lib/vulkan/utility/ix.sh', KHRONOS + 'Vulkan-Utility-Libraries'),
        sdk('lib/vulkan/validation', 'lib/vulkan/validation/ix.sh', KHRONOS + 'Vulkan-ValidationLayers'),
        sdk('bin/vulkan/tools', 'bin/vulkan/tools/t/ix.sh', KHRONOS + 'Vulkan-Tools'),
        # lib/spirv/tools fetches these headers too, through the same ver.sh.
        sdk('lib/spirv/headers', 'lib/spirv/headers/ver.sh', KHRONOS + 'SPIRV-Headers', literal=True),
        sdk('lib/spirv/tools', 'lib/spirv/tools/ix.sh', KHRONOS + 'SPIRV-Tools'),
        sdk('lib/spirv/cross', 'lib/spirv/cross/ix.sh', KHRONOS + 'SPIRV-Cross'),
        sdk('lib/volk', 'lib/volk/ix.sh', GH + 'zeux/volk'),
    )),
)


def owned(packages, groups=GROUPS):
    return any(m.owns(p) for g in groups for m in g.members for p in packages)


class Groups:
    def __init__(self, updater, net, log, failure, groups=GROUPS):
        self.updater = updater
        self.net = net
        self.log = log
        self.failure = failure
        self.groups = groups
        self.pkgs = updater.repo / 'pkgs'

    def run(self):
        done = failed = 0

        for group in self.groups:
            try:
                if self.group(group):
                    done += 1
            except self.failure as exc:
                self.log(f'FAILED {group.name}: {exc}')
                failed += 1
            except OSError as exc:
                self.log(f'FAILED {group.name}: cannot list releases: {exc}')
                failed += 1
            finally:
                self.updater.restore()

        self.log(f'groups done: updated={done} failed={failed}')

    def group(self, group):
        ours = {}

        for m in group.members:
            path = self.pkgs / m.holder
            version = m.version_in(path.read_text()) if path.is_file() else None

            if version is None:
                raise self.failure(f'no version in {m.holder}')

            ours[m] = version

        released = {m: group.releases(self.net.tags(m.repo), m) for m in group.members}
        common = set.intersection(*released.values())

        newest = max(set.union(*released.values()), key=numeric, default=None)
        target = max(common, key=numeric, default=None)

        if newest and newest != target:
            waiting = [m.directory for m in group.members if newest not in released[m]]
            self.log(f'{group.name} {newest}: not released by {", ".join(waiting)} yet')

        if not target:
            return False

        behind = [m for m in group.members if numeric(ours[m]) < numeric(target)]

        if not behind:
            return False

        self.log(f'{group.name} {target}: ' + ', '.join(f'{m.directory} {ours[m]}' for m in behind))
        self.updater.bump_group([(m.holder, ours[m], target, m.literal) for m in behind], [m.directory for m in behind])
        # What CI builds, the way it builds it.
        self.updater.render(['set/ci'], ('--seed=1',))
        self.updater.publish(f'{group.name} {target}: ' + ', '.join(f'{m.directory} {ours[m]}' for m in behind))

        return True
