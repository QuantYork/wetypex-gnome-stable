#!/usr/bin/env python3
"""Restore only package-managed files; preserve user edits and personal data."""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile

UNIT = 'wetypex-gnome-stable.service'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stage-home', type=pathlib.Path, help='Undo a staged test, without desktop changes')
    args = p.parse_args()
    home = (args.stage_home or pathlib.Path.home()).resolve()
    state = home / '.local/state/wetypex-gnome-stable'
    path = state / 'installation.json'
    if not path.exists():
        raise SystemExit('No installation manifest found.')
    manifest = json.loads(path.read_text())
    if manifest['home'] != str(home) or manifest['staged'] != bool(args.stage_home):
        raise SystemExit('Manifest does not match the requested home/mode.')
    backup = pathlib.Path(manifest['backup'])
    if not args.stage_home:
        subprocess.run(['systemctl', '--user', 'disable', '--now', UNIT], check=True)
    retained = []
    for entry in manifest['files']:
        rel = pathlib.PurePosixPath(entry['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise SystemExit('Invalid manifest path.')
        target = home / rel
        if target.is_symlink() or (target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != entry['sha256']):
            retained.append(str(target))
            continue
        if entry['existed']:
            source = backup / rel
            fd, temporary = tempfile.mkstemp(prefix='.restore-', dir=target.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(source.read_bytes())
                os.chmod(temporary, source.stat().st_mode & 0o777)
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary): os.unlink(temporary)
        elif target.exists():
            target.unlink()
    if not args.stage_home:
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    if retained:
        print('Preserved modified files; keep manifest for manual recovery:')
        print('\n'.join(retained))
    else:
        path.rename(state / 'last-uninstalled.json')
    print('Backups retained at:', backup)
    print('Input engine, dictionaries, pairing data and GNOME extensions were not removed.')
    if not args.stage_home:
        print('Start your preferred input method or log in again. Kimpanel can be disabled separately if desired.')

if __name__ == '__main__':
    main()
