#!/usr/bin/python3
import importlib.util,json,os,pathlib,sys,tempfile,time
src=pathlib.Path(__file__).resolve().parents[1]/'src';sys.path.insert(0,str(src));from voice_status import VoiceStatus,view,process_matches,process_identity
with tempfile.TemporaryDirectory(prefix='voice-indicator-state-') as t:
 root=pathlib.Path(t);j={'dir':root/'session-a','record':type('Fake',(),{'pid':os.getpid()})()};v=VoiceStatus(root)
 v.event(j,'record_requested');d=json.loads(v.path.read_text());now=d['updated'];assert view(d,now,False,True)['title']=='正在准备录音'
 v.event(j,'recording_started');d=json.loads(v.path.read_text());start=d['record_started'];assert view(d,start+65,True,True)['clock']=='01:05'
 # A heartbeat must keep a long recording visible and never expose transcript content.
 v.heartbeat();d=json.loads(v.path.read_text());assert view(d,d['updated']+.2,True,True)['title']=='正在录音'
 assert not set(d)&{'text','audio','token','identity','transcript'}
 # Process failure is a visible error, not an apparently healthy recording.
 d['updated']=100;d['record_started']=90
 assert view(d,105,True,False)['color']=='error';assert view(d,500,True,False) is not None
 assert view(d,105,False,False)['title']=='录音状态已中断';assert view(d,120,False,False) is None
 assert not process_matches(os.getpid(),'wrong-start-time');assert process_matches(os.getpid(),process_identity(os.getpid()))
 v.event(j,'recorder_stopped');d=json.loads(v.path.read_text());assert view(d,d['updated'],False,True)['detail']=='麦克风已关闭'
 assert view(d,d['updated'],True,True)['title']=='录音仍在进行'
 v.event(j,'submit_requested');d=json.loads(v.path.read_text());assert view(d,d['updated'],False,True)['detail']=='录音已停止 · 完成后发送'
 v.event(j,'result_ready');d=json.loads(v.path.read_text());assert view(d,d['updated'],False,True)['title']=='文字已输入';assert view(d,d['expires']+.1,False,True) is None
 v.event(j,'stream_failed_or_timed_out');d=json.loads(v.path.read_text());assert view(d,d['updated'],False,True)['color']=='error'
 other={'dir':root/'session-b'};v.event(other,'record_requested');v.event(j,'cancelled');assert json.loads(v.path.read_text())['session']=='session-b'
 assert view(None) is None and view({'phase':'recording','updated':'invalid'}) is None
 assert v.path.stat().st_mode&0o777==0o600
print('PASS: continuous recording, real elapsed time, processing/completion, stale heartbeat, live orphan warning, PID reuse, old-session isolation and private status; no microphone/network')
