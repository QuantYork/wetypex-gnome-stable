#!/usr/bin/python3
"""Add Win/Command+X/Z to the existing keyd mapping without replacing other keys."""
import datetime
import difflib
import os
import pathlib
import shutil
import subprocess
import tempfile
import sys

CONFIG = pathlib.Path('/etc/keyd/win-copy-paste.conf')
KEYD = '/usr/bin/keyd.rvaiya'


def render(text):
    lines = text.splitlines(keepends=True)
    sections = [i for i,line in enumerate(lines) if line.strip() == '[meta]']
    if len(sections) != 1:
        raise ValueError('Expected exactly one existing [meta] section; no change made.')
    start = sections[0]+1
    end = next((i for i in range(start,len(lines)) if lines[i].strip().startswith('[')),len(lines))
    found = set()
    for line in lines[start:end]:
        body = line.split('#',1)[0].strip()
        if '=' not in body: continue
        key,value = (part.strip() for part in body.split('=',1))
        if key in ('x','z'):
            if value != 'C-'+key: raise ValueError(f'Existing meta+{key} has a different mapping; no change made.')
            if key in found: raise ValueError(f'Duplicate meta+{key} mapping; no change made.')
            found.add(key)
    additions = [key+' = C-'+key+'\n' for key in ('x','z') if key not in found]
    if additions:
        if start > 0 and not lines[start-1].endswith('\n'):lines[start-1]+='\n'
        lines[start:start]=additions
    return ''.join(lines)


def main():
    if CONFIG.is_symlink() or not CONFIG.is_file():raise SystemExit('Existing regular keyd mapping file required.')
    old=CONFIG.read_text();new=render(old)
    if '--dry-run' in sys.argv:
        print(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=str(CONFIG),tofile=str(CONFIG))),end='')
        return
    if os.geteuid()!=0:raise SystemExit('Administrator authorization required; run with pkexec.')
    if old==new:print('Win/Command+X/Z are already configured.');return
    directory=pathlib.Path('/var/backups/wetypex-gnome-stable');directory.mkdir(mode=0o755,parents=True,exist_ok=True)
    backup=directory/('keyd-before-cut-undo-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.conf')
    shutil.copy2(CONFIG,backup)
    fd,temp=tempfile.mkstemp(prefix='.keyd-shortcuts-',dir=CONFIG.parent)
    try:
        with os.fdopen(fd,'w') as stream:stream.write(new)
        os.chmod(temp,CONFIG.stat().st_mode & 0o777);os.chown(temp,0,0);os.replace(temp,CONFIG)
        try:subprocess.run([KEYD,'reload'],check=True)
        except subprocess.CalledProcessError:
            shutil.copy2(backup,CONFIG);subprocess.run([KEYD,'reload'],check=False)
            raise SystemExit('Reload failed; original mapping restored.')
    finally:
        if os.path.exists(temp):os.unlink(temp)
    print('Added Win/Command+X → Ctrl+X and Win/Command+Z → Ctrl+Z.')
    print('Backup:',backup)

if __name__=='__main__':main()
