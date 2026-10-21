#!/usr/bin/python3
"""Run the original account transport sandbox without logging speech or credentials."""
import fcntl,os,pathlib,subprocess,sys,time

def main():
    os.umask(0o077)
    base=pathlib.Path(os.environ.get('XDG_DATA_HOME',str(pathlib.Path.home()/'.local/share')))/'fcitx5-wetypex'
    state=pathlib.Path(os.environ.get('WETYPE_ACCOUNT_STATE_DIR',str(base/'account')))
    runtime=pathlib.Path(os.environ.get('WETYPE_RUNTIME_DIR',str(base/'runtime')))
    support=pathlib.Path(os.environ.get('WETYPE_STREAM_SUPPORT',str(pathlib.Path(__file__).resolve().parent/'stream-support')))
    if not (runtime/'manifest.txt').is_file():return 78
    (state/'business').mkdir(mode=0o700,parents=True,exist_ok=True)
    with (state/'account.lock').open('a') as lock:
        deadline=time.monotonic()+20
        while True:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>deadline:return 73
                time.sleep(.05)
        model=pathlib.Path('/sys/class/dmi/id/product_name')
        model=model.read_text().strip() if model.exists() else 'LINUX'
        args=['bwrap','--unshare-pid','--die-with-parent','--ro-bind','/usr','/usr','--symlink','usr/lib','/lib','--ro-bind','/lib64','/lib64','--symlink','usr/bin','/bin','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/etc']
        for path in ('/etc/resolv.conf','/etc/hosts','/etc/nsswitch.conf'):args+=['--ro-bind',path,path]
        for path in ('/etc/ssl','/etc/pki','/etc/ca-certificates'):args+=['--ro-bind-try',path,path]
        args+=['--ro-bind',str(runtime),'/input','--ro-bind',str(support),'/support','--bind',str(state),'/work','--chdir','/work','--clearenv']
        values={'PATH':'/usr/bin','HOME':'/work','WETYPE_SUPPORT_DIR':'/support','WETYPE_DEVICE_MODEL':model or 'LINUX','WETYPE_WORK_DIR':'/work/business','WETYPE_IDENTITY_FILE':'/work/identity.json','WETYPE_NETWORK_LIVE':'1','WETYPE_VOICE_STREAM':'1','WETYPE_VOICE_POLISH':os.environ.get('WETYPE_VOICE_POLISH','1')}
        for key,value in values.items():args+=['--setenv',key,value]
        args+=['/support/wetypex-engine-host','/input','business-service']
        # Keep the account lock alive while the child runs. Its stdout is the private stream.
        return subprocess.call(args,stderr=subprocess.DEVNULL)
if __name__=='__main__':raise SystemExit(main())
