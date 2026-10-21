#!/usr/bin/env python3
"""Exercise the helper with fake recorder/encoder/account/notifications; no audio/network."""
import importlib.util,json,os,pathlib,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('voice_feedback',root/'scripts/improve-voice-feedback.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source=pathlib.Path('/usr/bin/fcitx5-wetypex-voice').read_text()
patched=m.render(source);assert m.render(patched)==patched
with tempfile.TemporaryDirectory(prefix='voice-feedback-test-') as d:
 p=pathlib.Path(d);bin=p/'bin';bin.mkdir();state=p/'state';config=p/'config';config.mkdir()
 def executable(name,body):
  path=bin/name;path.write_text(body);path.chmod(0o755)
 executable('pw-record','#!/bin/sh\nfor last do :; done\nprintf synthetic-audio > "$last"\n')
 executable('ffmpeg','#!/bin/sh\nfor last do :; done\nprintf synthetic-opus > "$last"\n')
 executable('notify-send','#!/bin/sh\nprintf "%s\\n" "$*" >> "$NOTIFY_LOG"\necho 77\n')
 executable('fake-account','#!/usr/bin/python3\nimport json,os,sys\nif os.environ.get("MOCK_FAIL"):sys.exit(1)\nprint(json.dumps({"ok":True,"text":"语音提示测试。"}))\n')
 helper=p/'voice.sh';helper.write_text(patched.replace('/usr/bin/fcitx5-wetypex-account','fake-account'))
 subprocess.run(['sh','-n',helper],check=True)
 env=os.environ.copy();env.update(PATH=str(bin)+':'+env['PATH'],WETYPE_STATE_DIR=str(state),XDG_CONFIG_HOME=str(config),NOTIFY_LOG=str(p/'notifications'))
 subprocess.run(['sh',helper,'start'],env=env,check=True)
 # Wait only for the fake recorder's output, never access an audio device.
 import time
 for i in range(100):
  if (state/'voice/input.wav').exists():break
  time.sleep(.01)
 subprocess.run(['sh',helper,'stop','0','0'],env=env,check=True)
 data=(state/'voice-inbox.json').read_bytes();assert data.isascii() and json.loads(data)['text']=='语音提示测试'
 notifications=(p/'notifications').read_text();assert all(s in notifications for s in ['正在录音','正在识别','识别完成'])
 timings=(state/'voice/latency.log').read_text();assert 'recognition_finished' in timings and 'result_ready' in timings
 assert '语音提示测试' not in timings and '语音提示测试' not in notifications
 # A missing/empty recording must produce a failure notice without recognition.
 (state/'voice/recording').write_text('999999999\n');(state/'voice/input.wav').unlink()
 failed=subprocess.run(['sh',helper,'stop','0','0'],env=env)
 assert failed.returncode!=0 and '语音输入失败' in (p/'notifications').read_text()
 print('PASS: recording/recognition/success/failure notices, timing only, ASCII inbox; no real audio/network')
