#!/usr/bin/python3
"""Own each recording/recognition lifecycle. Never log speech or account replies."""
import asyncio,contextlib,fcntl,json,os,pathlib,signal,socket,struct,subprocess,sys,time,uuid
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from voice_status import VoiceStatus,process_matches

def format_voice_text(text, mode):
    if mode == '添加完整标点':
        text = text.rstrip()
        # Preserve returned punctuation; insert before trailing closing quotes.
        closing = '”’」』）》】\"\''
        core = text.rstrip(closing)
        if core and core[-1] not in '。！？!?.,，、；;：:…':
            text = core + '。' + text[len(core):]
    elif mode in ('智能标点', '句末不加句号'):
        text = text.rstrip()
        if text.endswith(('。', '.')):
            text = text[:-1]
    elif mode == '空格替换标点':
        import re
        text = re.sub(r'[，。！？；：、,.!?;:]+', ' ', text)
    return text

class VoiceService:
    def __init__(self,root,tools=None,notify=True,budget=45):
        self.root=pathlib.Path(root);self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.tools=tools or {'record':'pw-record','encode':'ffmpeg','account':'/usr/bin/fcitx5-wetypex-account'}
        self.notify_enabled=notify;self.budget=budget;self.lock=asyncio.Lock();self.current=None;self.notice=0;self.closed=[];self.ui=VoiceStatus(self.root)
    def mark(self,job,event):
        with (job['dir']/'timing.log').open('a') as f:f.write(f'{time.monotonic():.3f} {event}\n')
        self.ui.event(job,event)
    async def notify(self,message):
        if not self.notify_enabled:return
        try:
            ready=json.loads((self.root/'indicator-ready.json').read_text())
            if time.monotonic()-float(ready['updated'])<3 and process_matches(ready['pid'],ready['identity']):return
        except (OSError,ValueError,TypeError,KeyError):pass
        try:
            p=await asyncio.create_subprocess_exec('notify-send','--app-name=WeTypeX','--icon=audio-input-microphone',f'--replace-id={self.notice}','--print-id','语音输入',message,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
            try:
                out,_=await asyncio.wait_for(p.communicate(),2)
                if out.strip().isdigit():self.notice=int(out.strip())
            finally:
                if p.returncode is None:p.kill();await p.wait()
        except (OSError,asyncio.TimeoutError):pass
    async def terminate(self,p,initial=signal.SIGTERM):
        if not p or p.returncode is not None:return
        for sig,seconds in [(initial,1),(signal.SIGTERM,.5),(signal.SIGKILL,1)]:
            # Signal the complete subprocess group, including account sandbox children.
            with contextlib.suppress(ProcessLookupError):os.killpg(p.pid,sig)
            try:await asyncio.wait_for(asyncio.shield(p.wait()),seconds);return
            except asyncio.TimeoutError:pass
    def erase_audio(self,j):
        for name in ('input.wav','input.opus'):(j['dir']/name).unlink(missing_ok=True)
    async def cancel_locked(self):
        j=self.current
        if not j:return
        self.publish(j,'cancel');self.current=None;j['cancelled']=True
        task=j.get('task')
        if task:task.cancel()
        await self.terminate(j.get('record'),signal.SIGINT)
        await self.terminate(j.get('worker'))
        await self.terminate(j.get('encoder'))
        await self.terminate(j.get('transport'))
        if task:
            with contextlib.suppress(asyncio.CancelledError):await task
        self.erase_audio(j);self.mark(j,'cancelled')
    async def command(self,action,token):
        async with self.lock:
            if action=='status':return {'ok':True,'phase':self.current['phase'] if self.current else 'idle'}
            if action in ('stop','cancel'):
                if token not in self.closed:self.closed.append(token)
                self.closed=self.closed[-256:]
            if action=='cancel-all' or action=='cancel':
                if self.current and (action=='cancel-all' or self.current['token']==token):
                    await self.cancel_locked();await self.notify('语音输入已取消，麦克风已释放')
                return {'ok':True}
            if action=='submit':
                if self.current and self.current['token']==token:self.mark(self.current,'submit_requested')
                return {'ok':True}
            if action=='start':
                if token in self.closed:return {'ok':True,'ignored':True}
                if self.current and self.current['token']==token and self.current['phase']=='recording':return {'ok':True}
                await self.cancel_locked()
                folder=self.root/'sessions'/uuid.uuid4().hex;folder.mkdir(mode=0o700,parents=True)
                j={'token':token,'dir':folder,'phase':'recording','cancelled':False};self.current=j;self.mark(j,'record_requested')
                cfg={}
                try:cfg=json.loads((pathlib.Path(os.environ.get('XDG_CONFIG_HOME',str(pathlib.Path.home()/'.config')))/'fcitx5/wetypex.json').read_text())
                except (OSError,ValueError):pass
                j['config']=cfg;args=[self.tools['record'],'--rate','16000','--channels','1','--format','s16']
                mic=cfg.get('voice_microphone','自动检测')
                if mic and mic!='自动检测':args+=['--target',str(mic)]
                if cfg.get('voice_streaming',False):
                    j['stop_event']=asyncio.Event()
                    j['task']=asyncio.create_task(self.stream_recognize(j,args))
                    await self.notify('正在录音并实时识别…')
                    return {'ok':True}
                try:
                    with (folder/'recorder.log').open('wb') as log:
                        j['record']=await asyncio.create_subprocess_exec(*args,str(folder/'input.wav'),stdout=log,stderr=log,start_new_session=True)
                    self.mark(j,'recording_started');j['watch']=asyncio.create_task(self.watch_record(j))
                    await self.notify('正在录音；松开按住说话快捷键，或在持续录音模式按普通键结束')
                    return {'ok':True}
                except OSError:
                    await self.cancel_locked();self.mark(j,'recording_failed');await self.notify('录音启动失败，请检查麦克风');return {'ok':False}
            if action=='stop':
                j=self.current
                if not j or j['token']!=token or j['phase']!='recording':return {'ok':True,'ignored':True}
                j['phase']='recognizing';self.mark(j,'stop_requested')
                if 'stop_event' in j:
                    j['stop_event'].set()
                    await self.terminate(j.get('record'),signal.SIGINT);self.mark(j,'recorder_stopped')
                    await self.notify('麦克风已释放，正在确认最终文字…');return {'ok':True}
                await self.terminate(j['record'],signal.SIGINT);self.mark(j,'recorder_stopped')
                j['task']=asyncio.create_task(self.recognize(j));await self.notify('麦克风已释放，正在识别…');return {'ok':True}
            return {'ok':False}
    async def watch_record(self,j):
        await j['record'].wait()
        if self.current is j and j['phase']=='recording':
            async with self.lock:
                if self.current is j and j['phase']=='recording':
                    await self.cancel_locked();await self.notify('录音意外停止，麦克风已释放')
    async def worker(self,j,args,capture=False,env=None):
        j['worker']=await asyncio.create_subprocess_exec(*args,stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,start_new_session=True,env=env)
        out,_=await j['worker'].communicate()
        if j['worker'].returncode:raise RuntimeError('worker failed')
        return out
    def publish(self,j,kind,text='',**extra):
        if self.current is not j or j['cancelled']:return
        target=self.root.parent/'voice-inbox.json';tmp=j['dir']/'inbox.tmp'
        data={'version':time.time_ns(),'kind':kind,'text':text,'session':j['token'][0],'epoch':j['token'][1],**extra}
        tmp.write_text(json.dumps(data,ensure_ascii=True)+'\n');tmp.chmod(0o600);tmp.replace(target)
    async def stream_recognize(self,j,record_args):
        children=[];tasks=[];group=None;stop_wait=None
        try:
            env=os.environ.copy();env.pop('LD_PRELOAD',None)
            env['WETYPE_VOICE_POLISH']='1' if j['config'].get('voice_smart_polish',True) else '0'
            launcher=self.tools.get('stream',str(pathlib.Path(__file__).resolve().parent/'voice-stream-launcher.py'))
            transport=await asyncio.create_subprocess_exec('/usr/bin/python3',launcher,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,start_new_session=True,env=env,limit=262144)
            j['transport']=transport;children.append(transport)
            encoder=await asyncio.create_subprocess_exec(self.tools['encode'],'-hide_banner','-loglevel','error','-probesize','32','-analyzeduration','1','-f','s16le','-ar','16000','-ac','1','-i','pipe:0','-c:a','libopus','-b:a','16k','-application','voip','-frame_duration','20','-page_duration','200000','-flush_packets','1','-f','ogg','pipe:1',stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,start_new_session=True)
            j['encoder']=encoder;children.append(encoder)
            if j['stop_event'].is_set():raise RuntimeError('stopped before capture')
            with (j['dir']/'recorder.log').open('wb') as log:
                recorder=await asyncio.create_subprocess_exec(*record_args,'--raw','-',stdout=asyncio.subprocess.PIPE,stderr=log,start_new_session=True)
            j['record']=recorder;children.append(recorder);self.mark(j,'recording_started')
            ready=asyncio.Event();j['last_text']='';j['verified_final']=False
            async def pcm():
                try:
                    while chunk:=await recorder.stdout.read(32768):encoder.stdin.write(chunk);await encoder.stdin.drain()
                    if j['phase']=='recording':raise RuntimeError('recorder exited unexpectedly')
                finally:
                    encoder.stdin.close()
                    with contextlib.suppress(BrokenPipeError,ConnectionResetError):await encoder.stdin.wait_closed()
            async def opus():
                await asyncio.wait_for(ready.wait(),22)
                packet=bytearray();number=0;audio_packets=0
                async def send(data,end=False):
                    transport.stdin.write((json.dumps({'audio_hex':data.hex(),'end':end})+'\n').encode());await transport.stdin.drain()
                while True:
                    try:header=await encoder.stdout.readexactly(27)
                    except asyncio.IncompleteReadError as e:
                        if e.partial:raise RuntimeError('truncated Ogg')
                        break
                    if header[:4]!=b'OggS':raise RuntimeError('bad Ogg')
                    laces=await encoder.stdout.readexactly(header[26]);body=await encoder.stdout.readexactly(sum(laces));offset=0;raw=bytearray()
                    for size in laces:
                        packet.extend(body[offset:offset+size]);offset+=size
                        if size<255:
                            number+=1
                            if number==1 and not packet.startswith(b'OpusHead'):raise RuntimeError('bad Opus head')
                            if number==2 and not packet.startswith(b'OpusTags'):raise RuntimeError('bad Opus tags')
                            if number>2:
                                if not 0<len(packet)<=1500:raise RuntimeError('bad Opus frame')
                                if not audio_packets:raw.extend(b'#!OPUS_RAW_V1'+bytes([2,1,0]))
                                raw.extend(len(packet).to_bytes(2,'little'));raw.extend(packet);audio_packets+=1
                            packet.clear()
                    if raw:await send(bytes(raw))
                if packet or not audio_packets:raise RuntimeError('empty/truncated audio')
                await encoder.wait()
                if encoder.returncode:raise RuntimeError('encoding failed')
                await send(b'',True);self.mark(j,'audio_end_sent')
            async def results():
                while True:
                    line=await transport.stdout.readline()
                    if not line:raise RuntimeError('transport closed before final result')
                    message=json.loads(line);kind=message.get('type');text=message.get('text','')
                    if not isinstance(text,str) or len(text.encode())>60000:raise RuntimeError('invalid result')
                    if kind=='ready':ready.set()
                    elif kind=='partial' and text:
                        if not j['last_text']:self.mark(j,'first_partial')
                        j['last_text']=text;self.publish(j,'partial',text)
                    elif kind=='final':
                        if not text:raise RuntimeError('empty final result')
                        text=format_voice_text(text,j['config'].get('voice_punctuation','智能标点'))
                        j['verified_final']=bool(message.get('verified_final'))
                        self.publish(j,'final',text,verified_final=j['verified_final']);self.mark(j,'result_ready' if j['verified_final'] else 'result_ready_without_verified_final')
                        return
                    elif kind=='error':raise RuntimeError('transport failed')
            tasks=[asyncio.create_task(pcm()),asyncio.create_task(opus()),asyncio.create_task(results())]
            group=asyncio.gather(*tasks);stop_wait=asyncio.create_task(j['stop_event'].wait())
            async with asyncio.timeout(630):
                done,_=await asyncio.wait([group,stop_wait],return_when=asyncio.FIRST_COMPLETED)
                if stop_wait in done:await asyncio.wait_for(group,45)
                else:await group
            if self.current is j:self.current=None
            await self.notify('识别完成' if j['verified_final'] else '识别完成；最终润色未确认，已保留当前结果')
        except asyncio.CancelledError:raise
        except Exception:
            if self.current is j:
                self.publish(j,'error');self.current=None;self.mark(j,'stream_failed_or_timed_out')
                await self.notify('实时识别失败，录音已停止；可以重新录音')
        finally:
            if group:group.cancel()
            if stop_wait:stop_wait.cancel()
            for task in tasks:task.cancel()
            for p in reversed(children):await self.terminate(p,signal.SIGINT if p is j.get('record') else signal.SIGTERM)
            for task in [*tasks,*([stop_wait] if stop_wait else [])]:
                with contextlib.suppress(asyncio.CancelledError,Exception):await task
            if group:
                with contextlib.suppress(asyncio.CancelledError,Exception):await group
            self.erase_audio(j);self.mark(j,'stream_cleanup_finished')

    async def recognize(self,j):
        try:
            async with asyncio.timeout(self.budget):
                wav=j['dir']/'input.wav';opus=j['dir']/'input.opus'
                if not wav.exists() or wav.stat().st_size<=44:raise RuntimeError('empty recording')
                await self.worker(j,[self.tools['encode'],'-hide_banner','-loglevel','error','-y','-i',str(wav),'-ar','16000','-ac','1','-c:a','libopus','-application','voip','-frame_duration','20',str(opus)])
                self.mark(j,'encoding_finished');env=os.environ.copy();env.pop('LD_PRELOAD',None)
                env['WETYPE_VOICE_POLISH']='1' if j['config'].get('voice_smart_polish',True) else '0'
                data=json.loads(await self.worker(j,[self.tools['account'],'voice-file',str(opus)],capture=True,env=env))
                self.mark(j,'recognition_finished')
                if not data.get('ok') or not data.get('text'):raise RuntimeError('recognition failed')
                text=format_voice_text(data['text'],j['config'].get('voice_punctuation','智能标点'))
                async with self.lock:
                    if self.current is not j or j['cancelled']:return
                    target=self.root.parent/'voice-inbox.json';tmp=j['dir']/'inbox.tmp'
                    tmp.write_text(json.dumps({'version':time.time_ns(),'text':text,'session':j['token'][0],'epoch':j['token'][1]},ensure_ascii=True)+'\n');tmp.chmod(0o600);tmp.replace(target)
                    self.current=None;self.mark(j,'result_ready')
                await self.notify('识别完成，结果已准备回填')
        except asyncio.CancelledError:raise
        except (Exception,):
            async with self.lock:
                if self.current is j:
                    self.publish(j,'error');self.current=None;self.mark(j,'failed_or_timed_out');await self.notify('识别失败或超时，已停止等待；可以重新录音')
        finally:
            await self.terminate(j.get('worker'));self.erase_audio(j)
    async def shutdown(self):
        async with self.lock:await self.cancel_locked()

async def serve(path):
    service=VoiceService(path.parent);done=asyncio.Event();loop=asyncio.get_running_loop()
    for sig in (signal.SIGTERM,signal.SIGINT):loop.add_signal_handler(sig,done.set)
    async def client(reader,writer):
        try:
            peer=writer.get_extra_info('socket').getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12)
            if struct.unpack('3i',peer)[1]!=os.getuid():return
            req=json.loads(await asyncio.wait_for(reader.readline(),2));token=tuple(int(x) for x in req.get('token',[0,0]))
            if len(token)!=2:raise ValueError()
            result=await service.command(req['action'],token)
            writer.write((json.dumps(result)+'\n').encode());await writer.drain()
        except Exception:pass
        finally:writer.close();await writer.wait_closed()
    path.unlink(missing_ok=True);server=await asyncio.start_unix_server(client,path=str(path),limit=4096);path.chmod(0o600)
    async def heartbeat():
        while True:
            await asyncio.sleep(1);service.ui.heartbeat()
    pulse=asyncio.create_task(heartbeat())
    try:await done.wait()
    finally:
        pulse.cancel()
        with contextlib.suppress(asyncio.CancelledError):await pulse
        server.close();await server.wait_closed();await service.shutdown();path.unlink(missing_ok=True)

def main():
    os.umask(0o077)
    root=pathlib.Path(os.environ.get('WETYPE_STATE_DIR',str(pathlib.Path(os.environ.get('XDG_DATA_HOME',str(pathlib.Path.home()/'.local/share')))/'fcitx5-wetypex/state')))/'voice'
    root.mkdir(mode=0o700,parents=True,exist_ok=True);path=root/'supervisor.sock'
    if sys.argv[1:]==['serve']:asyncio.run(serve(path));return
    action=sys.argv[1] if len(sys.argv)>1 else 'status';token=[int(x) for x in sys.argv[2:4]]
    if action in ('start','stop','cancel','submit') and len(token)!=2:raise SystemExit('Voice helper requires session and epoch.')
    req=json.dumps({'action':action,'token':token or [0,0]}).encode()+b'\n'
    with (root/'supervisor-start.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for attempt in range(40):
            try:
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(8);client.connect(str(path));client.sendall(req);reply=client.recv(4096)
                result=json.loads(reply);print(json.dumps(result));raise SystemExit(0 if result.get('ok') else 1)
            except (FileNotFoundError,ConnectionRefusedError):
                if action=='status':print(json.dumps({'ok':True,'phase':'idle'}));return
                if attempt==0:
                    env=os.environ.copy();env.pop('LD_PRELOAD',None)
                    subprocess.Popen(['/usr/bin/python3',str(pathlib.Path(__file__).resolve()),'serve'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env,start_new_session=True)
                time.sleep(.05)
        raise SystemExit('Voice supervisor did not start.')
if __name__=='__main__':main()
