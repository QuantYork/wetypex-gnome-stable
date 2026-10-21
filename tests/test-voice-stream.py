#!/usr/bin/python3
"""Local fake devices/transport only. FFmpeg encodes generated silence; no network."""
import asyncio,importlib.util,json,os,pathlib,tempfile
root=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('vs',root/'src/voice-supervisor.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
async def main():
 with tempfile.TemporaryDirectory(prefix='voice-stream-test-') as d:
  p=pathlib.Path(d);cfg=p/'config/fcitx5';cfg.mkdir(parents=True);(cfg/'wetypex.json').write_text(json.dumps({'voice_streaming':True,'voice_punctuation':'添加完整标点'}));os.environ['XDG_CONFIG_HOME']=str(p/'config')
  record=p/'record';record.write_text('''#!/usr/bin/python3
import os,signal,sys,time
signal.signal(signal.SIGINT,lambda *_:sys.exit(0))
while True:os.write(1,b'\\0'*640);time.sleep(.02)
''');record.chmod(0o755)
  stream=p/'transport.py';stream.write_text('''import json,sys
print(json.dumps({'type':'ready'}),flush=True)
n=0
for line in sys.stdin:
 d=json.loads(line);n+=1
 if d['end']:
  print(json.dumps({'type':'final','text':'测试完成？','verified_final':True}),flush=True);break
 print(json.dumps({'type':'partial','text':'测试前文' if n==1 else '修改前文'}),flush=True)
''')
  v=m.VoiceService(p/'state/voice',{'record':str(record),'encode':'ffmpeg','stream':str(stream)},notify=False)
  async def wait_partial():
   for _ in range(320):
    f=p/'state/voice-inbox.json'
    if f.exists() and json.loads(f.read_text()).get('kind')=='partial':return
    await asyncio.sleep(.025)
   raise AssertionError('No streaming partial result')
  await v.command('start',(1,1));j=v.current;await wait_partial();assert j['phase']=='recording'
  await v.command('stop',(1,1));await asyncio.wait_for(j['task'],5)
  final=json.loads((p/'state/voice-inbox.json').read_text());assert final['kind']=='final' and final['text']=='测试完成？' and final['verified_final']
  assert all(j[k].returncode is not None for k in ('record','encoder','transport'))
  (p/'state/voice-inbox.json').unlink()
  await v.command('start',(1,2));j=v.current;await wait_partial()
  await v.command('cancel',(1,1));assert v.current is j
  await v.command('cancel',(1,2));assert v.current is None
  assert all(j[k].returncode is not None for k in ('record','encoder','transport'))
  assert json.loads((p/'state/voice-inbox.json').read_text())['kind']=='cancel'
  await v.command('stop',(1,3));await v.command('start',(1,3));assert v.current is None
  await v.command('start',(1,4));j=v.current;await v.command('stop',(1,4));await asyncio.wait_for(j['task'],5);assert v.current is None
  await v.shutdown()
  print('PASS: streaming partial while recording, final punctuation, cancellation, stale token suppression, early stop, no leftover processes; fake devices, no network')
asyncio.run(main())
