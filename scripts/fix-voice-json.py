#!/usr/bin/python3
import datetime,os,pathlib,tempfile,shutil
p=pathlib.Path('/usr/bin/fcitx5-wetypex-voice')
if os.geteuid()!=0:raise SystemExit('Administrator authorization required.')
if p.is_symlink() or not p.is_file():raise SystemExit('Unexpected voice helper path.')
s=p.read_text();old='ensure_ascii=False) + "\\n")';new='ensure_ascii=True) + "\\n")'
if old not in s:
 if new in s:print('Voice JSON compatibility fix already installed.');raise SystemExit(0)
 raise SystemExit('Voice helper changed; refusing to edit an unknown version.')
if s.count(old)!=1:raise SystemExit('Ambiguous patch; no change made.')
backup=pathlib.Path('/var/backups/wetypex-gnome-stable');backup.mkdir(mode=0o755,parents=True,exist_ok=True)
b=backup/('voice-before-ascii-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sh');shutil.copy2(p,b)
fd,tmp=tempfile.mkstemp(prefix='.wetypex-voice-',dir=p.parent)
try:
 with os.fdopen(fd,'w') as f:f.write(s.replace(old,new,1))
 os.chmod(tmp,p.stat().st_mode & 0o777);os.chown(tmp,0,0);os.replace(tmp,p)
finally:
 if os.path.exists(tmp):os.unlink(tmp)
print('Changed only voice inbox JSON output to ASCII escapes.')
print('Original helper backup:',b)
