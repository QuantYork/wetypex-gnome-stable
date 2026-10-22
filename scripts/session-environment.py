"""Wait for the desktop's imported display environment before starting Fcitx."""
import os,pathlib,subprocess,time
KEYS=('DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS','XDG_SESSION_TYPE')
def ready(env):
    if not env.get('DISPLAY'):return False
    auth=env.get('XAUTHORITY')
    if not auth or not pathlib.Path(auth).is_file():return False
    wayland=env.get('WAYLAND_DISPLAY')
    if env.get('XDG_SESSION_TYPE')=='wayland' and not wayland:return False
    if wayland:
        path=pathlib.Path(wayland)
        if not path.is_absolute():path=pathlib.Path(env.get('XDG_RUNTIME_DIR','/nonexistent'))/path
        if not path.exists():return False
    return True

def manager_environment():
    result=subprocess.run(['/usr/bin/systemctl','--user','show-environment'],capture_output=True,text=True,timeout=1)
    if result.returncode:return {}
    return {k:v for line in result.stdout.splitlines() if '=' in line for k,v in [line.split('=',1)] if k in KEYS}

def prepare(env,budget=8,read_manager=manager_environment,sleep=time.sleep,clock=time.monotonic):
    env=env.copy()
    if ready(env):return env
    deadline=clock()+budget
    while True:
        try:env.update(read_manager())
        except (OSError,subprocess.SubprocessError):pass
        if ready(env):return env
        if clock()>=deadline:raise RuntimeError('Desktop display environment is not ready; retrying through the user service.')
        sleep(.2)
