#!/usr/bin/python3
import importlib.util,pathlib,tempfile
r=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('session_env',r/'scripts/session-environment.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as d:
 p=pathlib.Path(d);auth=p/'auth';auth.touch();(p/'wayland-test').touch()
 good={'DISPLAY':':test','XAUTHORITY':str(auth),'WAYLAND_DISPLAY':'wayland-test','XDG_RUNTIME_DIR':d,'XDG_SESSION_TYPE':'wayland'}
 assert m.ready(good) and not m.ready({})
 assert not m.ready(dict(good,XAUTHORITY='/missing'))
 t=[0];calls=[0]
 def sleep(x):t[0]+=x
 def manager():
  calls[0]+=1
  return {} if calls[0]<3 else good
 result=m.prepare({},read_manager=manager,sleep=sleep,clock=lambda:t[0]);assert result==good and calls[0]==3
 # A working inherited environment must not be replaced by a stale manager snapshot.
 assert m.prepare(good,read_manager=lambda: (_ for _ in ()).throw(AssertionError()))==good
 try:m.prepare({},budget=.4,read_manager=lambda:{},sleep=sleep,clock=lambda:t[0]);raise AssertionError('should not launch without a display')
 except RuntimeError:pass
print('PASS: delayed display import, existing valid session, missing authorization and bounded failure; no display changes')
