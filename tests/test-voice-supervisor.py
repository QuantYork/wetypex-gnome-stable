#!/usr/bin/python3
import asyncio,importlib.util,json,os,pathlib,signal,tempfile
root=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('vs',root/'src/voice-supervisor.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
full = '添加完整标点'
for source, expected in [('测试', '测试。'), ('测试。', '测试。'), ('真的吗？', '真的吗？'), ('好！', '好！'), ('测试…', '测试…'), ('“测试”', '“测试。”'), ('“测试？”', '“测试？”'), ('', ''), ('测试。  ', '测试。')]:
 assert m.format_voice_text(source, full) == expected
assert m.format_voice_text('测试。', '句末不加句号') == '测试'
async def test():
 with tempfile.TemporaryDirectory(prefix='voice-owner-test-') as d:
  p=pathlib.Path(d)
  os.environ['XDG_CONFIG_HOME']=str(p/'config')
  def exe(name,body):
   path=p/name;path.write_text(body);path.chmod(0o755);return str(path)
  record=exe('record', '''#!/usr/bin/python3
import signal,sys,time
open(sys.argv[-1],'wb').write(b'fake audio'*10)
signal.signal(signal.SIGINT,lambda *_:sys.exit(0))
while True:time.sleep(.01)
''')
  encode=exe('encode',"#!/usr/bin/python3\nimport sys\nopen(sys.argv[-1],'wb').write(b'fake opus')\n")
  account=exe('account',"#!/usr/bin/python3\nimport json\nprint(json.dumps({'ok':True,'text':'测试。'}))\n")
  tools={'record':record,'encode':encode,'account':account};v=m.VoiceService(p/'state/voice',tools,False,budget=.3)
  async def start(token):
   await v.command('start',token)
   for _ in range(100):
    if v.current and (v.current['dir']/'input.wav').exists():return
    await asyncio.sleep(.01)
  # Duplicate commands create only one owned recorder.
  await asyncio.gather(v.command('start',(1,1)),v.command('start',(1,1)))
  j=v.current;pid=j['record'].pid
  await start((1,1));assert v.current['record'].pid==pid
  await v.command('stop',(1,1));await asyncio.sleep(.15)
  if v.current:await v.current['task']
  inbox=p/'state/voice-inbox.json';assert inbox.read_bytes().isascii();assert json.loads(inbox.read_text())['text']=='测试'
  # Reordered release before press must not start a late recorder.
  await v.command('stop',(1,2));await v.command('start',(1,2));assert v.current is None
  await start((1,3));old=v.current
  await start((2,1));assert old['record'].returncode is not None
  # Old cancellation cannot affect a newer input context/session.
  await v.command('cancel',(1,3));assert v.current['token']==(2,1)
  await v.command('cancel',(2,1));assert v.current is None
  slow=exe('slow-account','#!/usr/bin/python3\nimport time\ntime.sleep(60)\n')
  v.tools['account']=slow
  await start((1,4));await v.command('stop',(1,4));j=v.current
  await j['task'];assert v.current is None and j['worker'].returncode is not None
  assert 'failed_or_timed_out' in (j['dir']/'timing.log').read_text()
  # Cancelling a recognition worker kills its group and never publishes a result.
  await start((1,5));await v.command('stop',(1,5));j=v.current
  await asyncio.sleep(.08);await v.command('cancel',(1,5));assert v.current is None
  assert j['record'].returncode is not None
  if j.get('worker'):assert j['worker'].returncode is not None
  await start((1,6));j=v.current;await v.shutdown();assert j['record'].returncode is not None
  print('PASS: one recorder, idempotent start, reorder suppression, stale cancel, ASCII delivery, timeout, cancel and shutdown; no audio/network')
asyncio.run(test())
