#!/usr/bin/python3
"""Install/restore only the optional GNOME panel display; do not change recognition."""
import argparse,datetime,hashlib,json,os,pathlib,shutil,subprocess,tempfile
from gi.repository import Gio
UUID='wetypex-voice-status@quantyork.local'
SERVICE='wetypex-voice-indicator.service'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(source,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.voice-panel-',dir=dest.parent);os.close(fd)
    try:shutil.copy2(source,tmp);os.replace(tmp,dest)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def main():
    p=argparse.ArgumentParser();p.add_argument('--restore',action='store_true');a=p.parse_args()
    if os.geteuid()==0:raise SystemExit('Run as the desktop user, without sudo.')
    repo=pathlib.Path(__file__).resolve().parents[1];home=pathlib.Path.home();lib=home/'.local/lib/wetypex-gnome-stable';state=home/'.local/state/wetypex-gnome-stable';manifest=state/'voice-panel-install.json'
    settings=Gio.Settings.new('org.gnome.shell');ext=home/'.local/share/gnome-shell/extensions'/UUID
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    if a.restore:
        if not manifest.exists():raise SystemExit('No panel installation manifest.')
        data=json.loads(manifest.read_text())
        subprocess.run(['gnome-extensions','disable',UUID],check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for key in ('enabled-extensions','disabled-extensions'):
            current=[v for v in settings.get_strv(key) if v!=UUID]
            if data[key]:current.append(UUID)
            settings.set_strv(key,current)
        Gio.Settings.sync()
        subprocess.run(['systemctl','--user','stop',SERVICE],check=True)
        if not data.get('service_enabled',True):subprocess.run(['systemctl','--user','disable',SERVICE],check=True)
        try:
            for item in reversed(data['files']):
                dest=pathlib.Path(item['path'])
                if not dest.exists():continue
                if sha(dest)!=item['installed_hash']:print('Preserving modified file:',dest);continue
                if item['backup']:replace(pathlib.Path(item['backup']),dest)
                else:dest.unlink()
            subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        finally:
            if data['service_active']:subprocess.run(['systemctl','--user','start',SERVICE],check=True)
        manifest.rename(manifest.with_name('voice-panel-restored-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.json'))
        print('Previous recording display restored. Recognition and keyboard shortcuts unchanged.')
        return
    if subprocess.check_output(['gnome-shell','--version'],text=True).strip()!='GNOME Shell 50.1':raise SystemExit('Only GNOME Shell 50.1 has been validated.')
    if not all((lib/name).is_file() for name in ['voice-supervisor.py','voice_status.py']):raise SystemExit('Install the matched streaming voice components first.')
    if manifest.exists():raise SystemExit('Panel display already managed; restore it before reinstalling.')
    backup=state/('voice-panel-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(mode=0o700)
    data={k:UUID in settings.get_strv(k) for k in ('enabled-extensions','disabled-extensions')}
    data['service_enabled']=subprocess.run(['systemctl','--user','is-enabled','--quiet',SERVICE]).returncode==0
    data['service_active']=subprocess.run(['systemctl','--user','is-active','--quiet',SERVICE]).returncode==0
    data['files']=[]
    sources=[(repo/'src/voice-indicator.py',lib/'voice-indicator.py')]+[(f,ext/f.name) for f in sorted((repo/'gnome'/UUID).iterdir()) if f.is_file()]
    unit=home/'.config/systemd/user'/SERVICE
    staged=backup/'panel.service';staged.write_text((repo/'systemd/wetypex-voice-indicator.service.in').read_text().replace('@ROOT@',str(lib)))
    sources.append((staged,unit))
    for n,(source,dest) in enumerate(sources):
        saved=backup/str(n)
        if dest.exists():shutil.copy2(dest,saved)
        data['files'].append({'path':str(dest),'backup':str(saved) if dest.exists() else None,'installed_hash':sha(source)})
    manifest.write_text(json.dumps(data,indent=2)+'\n');manifest.chmod(0o600)
    for source,dest in sources:replace(source,dest)
    settings.set_strv('disabled-extensions',[v for v in settings.get_strv('disabled-extensions') if v!=UUID])
    enabled=list(settings.get_strv('enabled-extensions'))
    if UUID not in enabled:settings.set_strv('enabled-extensions',enabled+[UUID])
    Gio.Settings.sync()
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','enable',SERVICE],check=True)
    subprocess.run(['systemctl','--user','restart',SERVICE],check=True)
    print('Installed; backup:',backup)
    result=subprocess.run(['gnome-extensions','info',UUID],capture_output=True,text=True)
    if result.returncode:print('New extension is not loaded by this Shell session. Log out and log in once; normal notifications remain available until then.')
    else:print(result.stdout)
if __name__=='__main__':main()
