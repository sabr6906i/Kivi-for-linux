#!/usr/bin/env python3
"""Build a deterministic, architecture-independent Debian binary package.

Uses only Python's standard library: no root access, dpkg, or host installation.
The archive layout follows deb(5): debian-binary, control.tar.gz, data.tar.gz.
"""
import argparse
import gzip
import hashlib
import io
import os
from pathlib import Path
import re
import tarfile


def tar_gz(files, epoch):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=epoch) as compressed:
        with tarfile.open(fileobj=compressed, mode='w', format=tarfile.GNU_FORMAT) as archive:
            for name, (contents, mode) in sorted(files.items()):
                info = tarfile.TarInfo('./' + name)
                info.size = len(contents)
                info.mode = mode
                info.mtime = epoch
                info.uid = info.gid = 0
                info.uname = info.gname = 'root'
                archive.addfile(info, io.BytesIO(contents))
    return output.getvalue()


def ar_member(name, contents, epoch):
    # SVR4/GNU short-name ar format; all Debian members have names <= 15 chars.
    header = f'{name + "/":<16}{epoch:<12}{0:<6}{0:<6}{"100644":<8}{len(contents):<10}`\n'.encode('ascii')
    if len(header) != 60:
        raise ValueError('Archive metadata exceeded the ar header field width.')
    return header + contents + (b'\n' if len(contents) % 2 else b'')


def package_files(root):
    files = {}
    app = 'usr/lib/bol-linux/'
    files[app + 'bol.py'] = ((root / 'kivi_linux.py').read_bytes(), 0o644)
    for path in sorted(root.glob('bol_*.py')):
        files[app + path.name] = (path.read_bytes(), 0o644)
    for folder in ('icons', 'themes'):
        for path in sorted((root / folder).glob('*.svg')):
            files[app + folder + '/' + path.name] = (path.read_bytes(), 0o644)
    files['usr/bin/bol'] = (b'#!/bin/sh\nexec /usr/bin/python3 /usr/lib/bol-linux/bol.py "$@"\n', 0o755)
    desktop = ('[Desktop Entry]\nType=Application\nName=Bol Voice Typing\n'
               'Comment=Voice typing and writing workspace\nExec=bol settings\n'
               'Icon=io.github.sabr6906i.Bol\nTerminal=false\nCategories=Utility;Accessibility;\n'
               'StartupNotify=true\n')
    files['usr/share/applications/io.github.sabr6906i.Bol.desktop'] = (desktop.encode(), 0o644)
    files['usr/share/icons/hicolor/scalable/apps/io.github.sabr6906i.Bol.svg'] = ((root / 'icons/brand.svg').read_bytes(), 0o644)
    for name in ('README.md', 'ROADMAP.md', 'LICENSE'):
        files['usr/share/doc/bol-linux/' + name] = ((root / name).read_bytes(), 0o644)
    for name in ('DESKTOPS.md', 'PACKAGES.md'):
        path = root / 'docs' / name
        if path.exists():
            files['usr/share/doc/bol-linux/' + name] = (path.read_bytes(), 0o644)
    files['usr/share/doc/bol-linux/copyright'] = ((root / 'packaging/debian/copyright').read_bytes(), 0o644)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='0.1.0~alpha1')
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, default=Path('dist'))
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]*', args.version) or ':' in args.version:
        parser.error('Use a Debian version without an epoch, e.g. 0.1.0~alpha1.')
    epoch = int(os.environ.get('SOURCE_DATE_EPOCH', '0'))
    if not 0 <= epoch <= 0xffffffff:
        parser.error('SOURCE_DATE_EPOCH must be between 0 and 4294967295.')
    root = args.source.resolve()
    files = package_files(root)
    control = (root / 'packaging/debian/control.in').read_text().replace('@VERSION@', args.version)
    size_kib = (sum(len(content) for content, _ in files.values()) + 1023) // 1024
    control += f'Installed-Size: {size_kib}\n'
    checksums = ''.join(hashlib.md5(content, usedforsecurity=False).hexdigest() + '  ' + name + '\n' for name, (content, _) in sorted(files.items()))
    control_files = {'control': (control.encode(), 0o644), 'md5sums': (checksums.encode(), 0o644)}
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / f'bol-linux_{args.version}_all.deb'
    contents = b'!<arch>\n'
    for name, content in [('debian-binary', b'2.0\n'), ('control.tar.gz', tar_gz(control_files, epoch)), ('data.tar.gz', tar_gz(files, epoch))]:
        contents += ar_member(name, content, epoch)
    destination.write_bytes(contents)
    print(destination.resolve())


if __name__ == '__main__':
    main()
