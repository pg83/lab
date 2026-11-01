"""GNU Bash/Readline releases: a base tarball followed by numbered patches.

The recipe's version includes the patch level, while fetch keeps the base
archive and every patch through that level. Recipes opt in after their unpack
step has been taught to apply the patches before package-specific changes.
"""

import hashlib
import re
from dataclasses import dataclass


MARKER = '# updater: gnu-patches'
VERSION = re.compile(r'(\d+\.\d+)(?:(?:\.?p|\.)(\d+))?')


@dataclass(frozen=True)
class Series:
    name: str
    package: str
    holder: str

    def owns(self, package):
        return package == self.package or package.startswith(self.package + '/')

    def base_url(self, base):
        return f'https://ftp.gnu.org/gnu/{self.name}/{self.name}-{base}.tar.gz'

    def patch_url(self, base, level):
        return (
            f'https://ftp.gnu.org/gnu/{self.name}/{self.name}-{base}-patches/'
            f'{self.name}{base.replace(".", "")}-{level:03d}'
        )


SERIES = (
    Series('bash', 'bin/bash/5', 'bin/bash/5/t/ix.sh'),
    Series('readline', 'lib/readline', 'lib/readline/ix.sh'),
)


def owner(packages):
    for package in packages:
        if match := re.match(r'bin/bash/(\d+)(?:/|$)', package):
            directory = f'bin/bash/{match[1]}'
            return Series('bash', directory, f'{directory}/t/ix.sh')

        if SERIES[1].owns(package):
            return SERIES[1]

    return None


def parse(version):
    match = VERSION.fullmatch(version)

    if not match or int(match[2] or 0) > 999:
        raise ValueError(f'unsupported GNU release version: {version}')

    return match[1], int(match[2] or 0)


def canonical(version):
    base, level = parse(version)
    return f'{base}p{level}' if level else base


def key(version):
    base, level = parse(version)
    return (*map(int, base.split('.')), level)


def block(name):
    return re.compile(r'(\{% block ' + name + r' %\}\n)(.*?)(\{% endblock %\})', re.S)


def content(text, name):
    matches = list(block(name).finditer(text))

    if len(matches) != 1:
        raise ValueError(f'expected one {name} block, got {len(matches)}')

    return matches[0][2].strip()


def replace(text, name, value):
    content(text, name)
    return block(name).sub(lambda m: m[1] + value + '\n' + m[3], text)


def pins(text):
    # Recognize the original recipes too: their tarball URL used version().
    base, _ = parse(content(text, 'version'))
    fetch = content(text, 'fetch').replace('{{self.version().strip()}}', base)
    return dict(re.findall(r'(?m)^(https://\S+)\n([0-9a-f]{64})\s*$', fetch))


def rewrite(text, series, version, net):
    if MARKER not in text or 'noauto' in text:
        raise ValueError(f'{series.package} is not enabled for GNU patch updates')

    base, level = parse(version)
    previous = pins(text)
    urls = [series.base_url(base)]
    urls.extend(series.patch_url(base, n) for n in range(1, level + 1))
    fetch = []

    for index, url in enumerate(urls):
        sha = previous.get(url)

        if sha is None:
            data = net.get(url, binary=True)

            if index:
                patch_id = url.rsplit('/', 1)[1].encode()
                release = series.name.title().encode() + b'-Release:'

                if not re.search(rb'(?m)^Patch-ID:[ \t]*' + re.escape(patch_id) + rb'[ \t]*\r?$', data):
                    raise ValueError(f'{url}: missing or incorrect Patch-ID')

                if not re.search(rb'(?m)^' + release + rb'[ \t]*' + re.escape(base.encode()) + rb'[ \t]*\r?$', data):
                    raise ValueError(f'{url}: incorrect release in patch header')

            sha = hashlib.sha256(data).hexdigest()

        fetch.extend((url, sha))

    text = replace(text, 'version', canonical(version))
    return replace(text, 'fetch', '\n'.join(fetch))
