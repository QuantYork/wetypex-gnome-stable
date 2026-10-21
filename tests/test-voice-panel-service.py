#!/usr/bin/python3
"""Private session bus and synthetic status only; never opens an audio device."""
import json,os,pathlib,signal,subprocess,sys,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
if '--isolated' not in sys.argv:
    raise SystemExit(subprocess.run(['dbus-run-session','--',sys.executable,__file__,'--isolated']).returncode)
sys.path.insert(0,str(ROOT/'src'))
from gi.repository import Gio,GLib
from voice_status import process_identity
BUS='io.github.QuantYork.WeTypeX.VoiceStatus';PATH='/io/github/QuantYork/WeTypeX/VoiceStatus'
with tempfile.TemporaryDirectory(prefix='voice-panel-test-') as d:
    root=pathlib.Path(d);env=os.environ.copy();env.pop('LD_PRELOAD',None)
    p=subprocess.Popen([sys.executable,str(ROOT/'src/voice-indicator.py'),'--state-dir',d],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
        for _ in range(100):
            owned=bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','NameHasOwner',GLib.Variant('(s)',(BUS,)),None,Gio.DBusCallFlags.NONE,1000,None).unpack()[0]
            if owned:break
            if p.poll() is not None:raise AssertionError(p.communicate())
            time.sleep(.02)
        assert owned and not (root/'indicator-ready.json').exists()
        def poll():return json.loads(bus.call_sync(BUS,PATH,BUS,'Poll',None,GLib.VariantType.new('(s)'),Gio.DBusCallFlags.NO_AUTO_START,1000,None).unpack()[0])
        assert poll() is None
        ready=json.loads((root/'indicator-ready.json').read_text());assert ready['surface']=='gnome-panel' and ready['pid']==p.pid
        assert (root/'indicator-ready.json').stat().st_mode&0o777==0o600
        now=time.monotonic();state={'phase':'recording','session':'synthetic','owner_pid':os.getpid(),'owner_identity':process_identity(os.getpid()),'recorder_pid':os.getpid(),'recorder_identity':process_identity(os.getpid()),'updated':now,'record_started':now-12,'record_stopped':None,'expires':None}
        def save(): (root/'indicator-state.json').write_text(json.dumps(state))
        save();display=poll();assert display['title']=='正在录音' and display['clock']=='00:12'
        assert not set(display)&{'transcript','audio','token','text'}
        state.update(phase='processing',recorder_pid=0,record_stopped=now,submit_requested=True);save();assert '完成后发送' in poll()['detail']
        state.update(phase='recording',recorder_pid=os.getpid(),updated=now-6);save();assert poll()['title']=='录音仍在进行'
        (root/'indicator-state.json').write_text('invalid');assert poll() is None
    finally:
        p.send_signal(signal.SIGTERM);stdout,stderr=p.communicate(timeout=3)
    assert p.returncode==0,(stdout,stderr)
    assert not (root/'indicator-ready.json').exists()
print('PASS: real private D-Bus publisher, consumer-only readiness, status privacy, elapsed time, queued submission, orphan warning, invalid input and clean shutdown; no microphone/network')
