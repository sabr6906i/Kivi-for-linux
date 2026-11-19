#!/usr/bin/env python3
"""Build Bol's noarch RPM with an already-installed Fedora rpmbuild toolchain.

This script never installs packages and never needs root. In a Fedora CI
container, provision rpm-build and python3 before invoking it.
"""
import argparse
import gzip
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='0.1.0')
    parser.add_argument('--release', default='0.1.alpha2')
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path('dist'))
    args = parser.parse_args()
    for value in (args.version, args.release):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+]*', value):
            parser.error('Version and release may contain only letters, digits, dots, underscores, and plus signs.')
    if not shutil.which('rpmbuild'):
        parser.exit(2, 'rpmbuild is missing. Use a Fedora build container with rpm-build and python3 installed; see docs/PACKAGES.md.\n')
    root = args.source.resolve()
    epoch = int(os.environ.get('SOURCE_DATE_EPOCH', '0'))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bol-rpmbuild-') as temporary:
        top = Path(temporary)
        for name in ('BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS'):
            (top / name).mkdir()
        prefix = f'bol-linux-{args.version}'
        source = top / 'SOURCES' / (prefix + '.tar.gz')
        paths = [root / 'kivi_linux.py', *sorted(root.glob('bol_*.py')), root / 'README.md', root / 'ROADMAP.md', root / 'LICENSE', root / 'docs/PACKAGES.md']
        for name in ('icons', 'themes'):
            paths.extend(sorted((root / name).glob('*.svg')))
        desktop_doc = root / 'docs/DESKTOPS.md'
        if desktop_doc.exists():paths.append(desktop_doc)
        # Stable member metadata; source contains no settings, tokens, audio, or backup files.
        def normalize(info):
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            info.mtime = epoch
            info.mode = 0o755 if info.isdir() else 0o644
            return info
        with source.open('wb') as raw:
            with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=epoch) as compressed:
                with tarfile.open(fileobj=compressed, mode='w', format=tarfile.GNU_FORMAT) as archive:
                    for path in paths:
                        archive.add(path, arcname=prefix + '/' + str(path.relative_to(root)), filter=normalize)
        spec = top / 'SPECS' / 'bol-linux.spec'
        shutil.copyfile(root / 'packaging/rpm/bol-linux.spec', spec)
        subprocess.run(['rpmbuild', '-bb', '--define', '_topdir ' + str(top), '--define', 'bol_version ' + args.version, '--define', 'bol_release ' + args.release, str(spec)], check=True)
        built = sorted((top / 'RPMS').rglob('*.rpm'))
        if not built:
            raise RuntimeError('rpmbuild did not produce an RPM.')
        for package in built:
            target = output / package.name
            shutil.copyfile(package, target)
            print(target)


if __name__ == '__main__':
    main()
