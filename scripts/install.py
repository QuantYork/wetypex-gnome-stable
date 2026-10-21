#!/usr/bin/env python3
"""Per-user atomic installation with a durable backup manifest."""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
UNIT = 'wetypex-gnome-stable.service'
UUID = 'kimpanel@kde.org'


def atomic_write(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.install-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--no-start', action='store_true', help='Enable next-login startup but do not restart now')
    p.add_argument('--stage-home', type=pathlib.Path, help='Test installation into a temporary home; no desktop changes')
    args = p.parse_args()
    stage = args.stage_home is not None
    home = (args.stage_home if stage else pathlib.Path.home()).resolve()
    if any(ch in str(home) for ch in ['\n', '\r', '%']):
        raise SystemExit('Home directory contains unsupported systemd path characters.')
    for name in ['libprekey-anchor.so', 'libcandidate-anchor.so', 'fcitx-version']:
        if not (ROOT / 'build' / name).is_file():
            raise SystemExit('Build first: python3 scripts/build.py')
    expected = (ROOT / 'build/fcitx-version').read_text().strip()
    if not stage:
        actual = subprocess.check_output(['fcitx5', '--version'], text=True).strip()
        if actual != expected:
            raise SystemExit(f'Runtime mismatch: built for {expected}, found {actual}')
        if not pathlib.Path('/usr/bin/fcitx5-wetypex-backend').is_file():
            raise SystemExit('Install and configure WeTypeX first; its engine is not included.')
        enabled = subprocess.check_output(['gnome-extensions', 'list', '--enabled'], text=True).splitlines()
        if UUID not in enabled:
            raise SystemExit('Install/enable Input Method Panel (kimpanel@kde.org) first; see README.')
        subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'graphical-session.target'], check=True)
    prefix = home / '.local/lib/wetypex-gnome-stable'
    state = home / '.local/state/wetypex-gnome-stable'
    state.mkdir(parents=True, exist_ok=True)
    manifest_path = state / 'installation.json'
    if manifest_path.exists():
        raise SystemExit('Already installed. Uninstall this version before reinstalling; backups are retained.')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = state / 'backups' / stamp
    backup.mkdir(parents=True)
    launcher = '.local/bin/wetypex-gnome-stable'
    unit_rel = '.config/systemd/user/' + UNIT
    # Install a user override to prevent an additional unpatched XDG fcitx5 launch.
    override = '.config/autostart/org.fcitx.Fcitx5.desktop'
    quoted_launcher = str(home / launcher).replace('\\', '\\\\').replace('"', '\\"')
    service = f'''[Unit]
Description=WeTypeX stable candidate positioning for GNOME
Documentation=https://github.com/QuantYork/wetypex-gnome-stable
PartOf=graphical-session.target
After=graphical-session-pre.target

[Service]
Type=simple
ExecStart="{quoted_launcher}" -r
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
'''
    files = {
        launcher: ((ROOT / 'scripts/wetypex-gnome-stable').read_bytes(), 0o755),
        unit_rel: (service.encode(), 0o644),
        override: (b'[Desktop Entry]\nType=Application\nName=Fcitx 5 (managed by wetypex-gnome-stable)\nHidden=true\n', 0o644),
    }
    for name in ['libprekey-anchor.so', 'libcandidate-anchor.so', 'fcitx-version']:
        files[str((prefix / name).relative_to(home))] = ((ROOT / 'build' / name).read_bytes(), 0o644)
    files[str((prefix / 'backend-json-compat.py').relative_to(home))] = ((ROOT / 'scripts/backend-json-compat.py').read_bytes(), 0o755)
    files[str((prefix / 'uninstall.py').relative_to(home))] = ((ROOT / 'scripts/uninstall.py').read_bytes(), 0o755)
    entries = []
    # Complete the backup plan before replacing the first managed file.
    for rel, (data, mode) in files.items():
        target = home / rel
        if target.is_symlink():
            raise SystemExit(f'Refusing to replace symlink: {target}')
        prior = target.exists()
        if prior:
            dest = backup / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
        entries.append({'path': rel, 'existed': prior, 'sha256': hashlib.sha256(data).hexdigest()})
    manifest = {'version': '0.1.0', 'home': str(home), 'backup': str(backup), 'files': entries, 'staged': stage}
    # Persist recovery metadata before mutations, so a partial install can be undone.
    atomic_write(manifest_path, json.dumps(manifest, indent=2).encode() + b'\n', 0o600)
    for rel, (data, mode) in files.items():
        atomic_write(home / rel, data, mode)
    if not stage:
        subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
        subprocess.run(['systemctl', '--user', 'enable', UNIT], check=True)
        if not args.no_start:
            subprocess.run(['systemctl', '--user', 'start', UNIT], check=True)
    print('Installed:', home / launcher)
    print('Backup:', backup)
    print('Uninstall:', prefix / 'uninstall.py')
    if stage:
        print('Staged only: no service or GNOME settings changed.')

if __name__ == '__main__':
    main()
