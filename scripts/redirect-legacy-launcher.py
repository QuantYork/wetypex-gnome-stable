#!/usr/bin/python3
"""Redirect the known early test launcher; preserve originals in the installer manifest."""
import argparse,hashlib,json,os,pathlib,shutil,tempfile
UNIT='wetypex-gnome-stable.service'
def write(p,data,mode):
 p.parent.mkdir(parents=True,exist_ok=True);fd,t=tempfile.mkstemp(prefix='.legacy-redirect-',dir=p.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(data)
  os.chmod(t,mode);os.replace(t,p)
 finally:
  if os.path.exists(t):os.unlink(t)
def main():
 p=argparse.ArgumentParser();p.add_argument('--stage-home',type=pathlib.Path);a=p.parse_args()
 if os.geteuid()==0:raise SystemExit('Run as the desktop user, without sudo.')
 home=(a.stage_home or pathlib.Path.home()).resolve();manifest=home/'.local/state/wetypex-gnome-stable/installation.json';data=json.loads(manifest.read_text());backup=pathlib.Path(data['backup'])
 legacy=home/'.local/bin/fcitx5-wetypex-fixed';desktop=home/'.local/share/applications/wetypex-fixed.desktop'
 managed={v['path'] for v in data['files']};changes=[]
 rel=str(legacy.relative_to(home))
 if legacy.exists() and rel not in managed:
  if legacy.is_symlink():raise SystemExit('Refusing legacy launcher symlink')
  old=legacy.read_text()
  if 'wetypex-compat/libcandidate-anchor.so' not in old or 'exec /usr/bin/fcitx5' not in old:raise SystemExit('Unknown legacy launcher; refusing replacement')
  changes.append((legacy,('#!/bin/sh\n# Use the same persistent service as the Fcitx 5 desktop icon.\nexec /usr/bin/systemctl --user restart '+UNIT+'\n').encode(),0o755))
 rel=str(desktop.relative_to(home))
 if desktop.exists() and rel not in managed:
  if desktop.is_symlink():raise SystemExit('Refusing legacy desktop symlink')
  lines=desktop.read_text().splitlines();expected='Exec='+str(legacy)+' -rd'
  if expected not in lines:raise SystemExit('Unknown legacy desktop command; refusing replacement')
  lines=[('Exec=/usr/bin/systemctl --user restart '+UNIT if v==expected else 'Name[zh_CN]=WeTypeX（稳定输入方案）' if v.startswith('Name[zh_CN]=') else v) for v in lines]
  changes.append((desktop,('\n'.join(lines)+'\n').encode(),0o644))
 for target,content,mode in changes:
  rel=str(target.relative_to(home));saved=backup/rel
  if saved.exists():raise SystemExit('Backup already exists: '+str(saved))
  saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,saved)
  data['files'].append({'path':rel,'existed':True,'sha256':hashlib.sha256(content).hexdigest()})
 if changes:
  write(manifest,json.dumps(data,indent=2).encode()+b'\n',0o600)
  for target,content,mode in changes:write(target,content,mode)
 print('Redirected legacy launch files:',len(changes));print('Originals retained in:',backup)
if __name__=='__main__':main()
