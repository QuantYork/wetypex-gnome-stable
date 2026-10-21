#!/usr/bin/python3
"""Build the opt-in, version-pinned voice components without modifying the source tree."""
import argparse,os,pathlib,shutil,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True,help='Clean fcitx5-wetypex 2.2.3.657-10 source');p.add_argument('--headers',type=pathlib.Path,default=pathlib.Path('/usr/include'),help='Matching Fcitx/LibIME/json-c include root');p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--test',action='store_true',help='Run the isolated actual-plugin voice/queued-Enter regression test, without audio or network');a=p.parse_args()
repo=pathlib.Path(__file__).resolve().parents[1];out=a.out.resolve();headers=a.headers.resolve();source=a.source.resolve()
if subprocess.check_output(['fcitx5','--version'],text=True).strip()!='5.1.19':raise SystemExit('Only Fcitx 5.1.19 has been validated.')
if not (source/'src/backend/macos_host.cpp').is_file():raise SystemExit('Source tree missing')
out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='wetypex-stream-build-') as t:
 stage=pathlib.Path(t);shutil.copytree(source/'src',stage/'src')
 patch=repo/'patches/wetypex-streaming-voice.patch'
 subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(patch)],cwd=stage,check=True)
 shutil.copy2(repo/'src/voice-stream.hpp',stage/'src/backend/voice_stream.hpp')
 subprocess.run(['g++','-std=c++17','-O2','-pthread','-I',str(headers),str(stage/'src/backend/macos_host.cpp'),'-o',str(out/'wetypex-engine-host'),'-l:libjson-c.so.5','-ldl'],check=True)
 cmd=['g++','-std=c++20','-O2','-Wall','-Wextra','-fPIC','-shared',str(stage/'src/plugin/wetype.cpp'),'-o',str(out/'wetypex.so'),'-Wl,-z,defs']
 for rel in ('Fcitx5/Core','Fcitx5/Config','Fcitx5/Utils','Fcitx5/Module/fcitx-module/clipboard','LibIME',''):cmd+=['-I',str(headers/rel)]
 for macro,tool in {'LAUNCHER':'backend','SETTINGS':'settings','SYNCD':'syncd','ACCOUNT_TOOL':'account','AI':'ai','VOICE':'voice','VMODE':'vmode','UPDATE':'update'}.items():cmd+=[f'-DWETYPE_{macro}="/usr/bin/fcitx5-wetypex-{tool}"']
 cmd+=['-DWETYPE_SYMBOLS="/usr/share/fcitx5-wetypex/wetypex-symbols.json"','-l:libFcitx5Core.so.7','-l:libFcitx5Config.so.6','-l:libFcitx5Utils.so.2','-l:libIMEPinyin.so.0','-l:libIMECore.so.0','-l:libjson-c.so.5']
 subprocess.run(cmd,check=True)
 if a.test:
  helper=stage/'fake-voice';helper.write_text('#!/bin/sh\nprintf "%s %s %s\\n" "$1" "$2" "$3" >> "$VOICE_CALL_LOG"\n');helper.chmod(0o755)
  testcmd=[x for x in cmd if x not in ('-fPIC','-shared')]
  testcmd[testcmd.index(str(stage/'src/plugin/wetype.cpp'))]=str(repo/'tests/test-stream-plugin.cpp')
  testcmd[testcmd.index(str(out/'wetypex.so'))]=str(out/'test-stream-plugin')
  testcmd+=['-I',str(stage/'src/plugin')]
  testcmd=[('-DWETYPE_VOICE="'+str(helper)+'"') if x.startswith('-DWETYPE_VOICE=') else ('-D'+x[2:].split('=')[0]+'="/bin/true"' if any(x.startswith('-DWETYPE_'+n+'=') for n in ('SYNCD','UPDATE','SETTINGS','VMODE')) else x) for x in testcmd]
  subprocess.run(testcmd,check=True)
  env=os.environ.copy();env.pop('LD_PRELOAD',None)
  for name in ('XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','FCITX_CONFIG_HOME','FCITX_DATA_HOME'):
   dest=stage/name;dest.mkdir();env[name]=str(dest)
  calls=stage/'calls';calls.touch();env.update(VOICE_CALL_LOG=str(calls),WETYPE_STATE_DIR=str(stage/'state'),WETYPE_BACKEND_LAUNCHER='/bin/false')
  subprocess.run([str(out/'test-stream-plugin')],env=env,timeout=30,check=True)
print('Built staging artifacts only. Nothing was installed:',out)
