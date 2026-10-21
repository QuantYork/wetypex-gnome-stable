#!/usr/bin/python3
"""Publish content-free voice status for the GNOME panel; never captures audio."""
import argparse,fcntl,json,os,pathlib,signal,tempfile,time
os.environ.pop('LD_PRELOAD',None)
from gi.repository import Gio,GLib
from voice_status import view,process_identity

BUS='io.github.QuantYork.WeTypeX.VoiceStatus'
PATH='/io/github/QuantYork/WeTypeX/VoiceStatus'
XML=f'''<node><interface name="{BUS}"><method name="Poll"><arg type="s" name="state" direction="out"/></method></interface></node>'''

class Publisher:
    def __init__(self,root):
        self.root=root;self.last_ready=0;self.registration=0;self.connection=None
    def read(self):
        try:
            p=self.root/'indicator-state.json'
            if p.stat().st_size>4096:return None
            return view(json.loads(p.read_text()))
        except (OSError,ValueError):return None
    def ready(self):
        now=time.monotonic()
        if now-self.last_ready<1:return
        self.last_ready=now
        fd,tmp=tempfile.mkstemp(prefix='.indicator-ready-',dir=self.root)
        try:
            with os.fdopen(fd,'w') as f:json.dump({'pid':os.getpid(),'identity':process_identity(os.getpid()),'updated':now,'surface':'gnome-panel'},f)
            os.chmod(tmp,0o600);os.replace(tmp,self.root/'indicator-ready.json')
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    def call(self,connection,sender,path,interface,method,params,invocation):
        if method!='Poll':
            invocation.return_dbus_error(BUS+'.UnknownMethod','Unknown method');return
        # Only a live consumer refreshes readiness. Without the extension, retain notifications.
        self.ready()
        invocation.return_value(GLib.Variant('(s)',(json.dumps(self.read(),ensure_ascii=True),)))
    def acquired(self,connection,name):
        self.connection=connection
        self.registration=connection.register_object(PATH,Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0],self.call,None,None)
    def close(self):
        if self.registration:self.connection.unregister_object(self.registration)
        p=self.root/'indicator-ready.json'
        try:
            if json.loads(p.read_text()).get('pid')==os.getpid():p.unlink()
        except (OSError,ValueError):pass

def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser();parser.add_argument('--state-dir',type=pathlib.Path);a=parser.parse_args()
    root=a.state_dir or pathlib.Path(os.environ.get('WETYPE_STATE_DIR',str(pathlib.Path(os.environ.get('XDG_DATA_HOME',str(pathlib.Path.home()/'.local/share')))/'fcitx5-wetypex/state')))/'voice'
    root.mkdir(parents=True,exist_ok=True,mode=0o700);lock=(root/'indicator.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return 0
    loop=GLib.MainLoop();publisher=Publisher(root)
    owner=Gio.bus_own_name(Gio.BusType.SESSION,BUS,Gio.BusNameOwnerFlags.NONE,publisher.acquired,None,lambda *_:loop.quit())
    for sig in (signal.SIGTERM,signal.SIGINT):GLib.unix_signal_add(GLib.PRIORITY_DEFAULT,sig,lambda:(loop.quit(),GLib.SOURCE_REMOVE)[1])
    try:loop.run()
    finally:publisher.close();Gio.bus_unown_name(owner)
    return 0
if __name__=='__main__':raise SystemExit(main())
