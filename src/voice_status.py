"""Content-free recording status and presentation policy; no GUI dependencies."""
import json,os,pathlib,tempfile,time

def process_identity(pid):
    try:
        fields=(pathlib.Path('/proc')/str(int(pid))/'stat').read_text().rsplit(')',1)[1].split()
        return fields[19] if fields[0] not in ('Z','X') else None
    except (OSError,ValueError,IndexError,TypeError):return None

def process_matches(pid,identity):
    return bool(identity) and process_identity(pid)==str(identity)

class VoiceStatus:
    def __init__(self,root):
        self.path=pathlib.Path(root)/'indicator-state.json';self.job=None;self.data=None
    def write(self):
        if not self.data:return
        self.data['updated']=time.monotonic()
        try:
            self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            fd,tmp=tempfile.mkstemp(prefix='.indicator-',dir=self.path.parent)
            try:
                with os.fdopen(fd,'w') as f:json.dump(self.data,f)
                os.chmod(tmp,0o600);os.replace(tmp,self.path)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        except OSError:pass # The indicator must never break recording/cleanup.
    def event(self,j,event):
        now=time.monotonic()
        if event=='record_requested':
            self.job=j;self.data={'version':1,'session':j['dir'].name,'phase':'starting','owner_pid':os.getpid(),'owner_identity':process_identity(os.getpid()),'record_started':None,'record_stopped':None,'recorder_pid':0,'recorder_identity':None,'expires':None,'submit_requested':False}
        if self.job is not j or not self.data:return
        d=self.data
        if event=='recording_started':
            d.update(phase='recording',record_started=now,recorder_pid=j['record'].pid,recorder_identity=process_identity(j['record'].pid))
        elif event=='submit_requested':d['submit_requested']=True
        elif event=='recorder_stopped':d.update(phase='processing',record_stopped=now)
        elif event=='result_ready':d.update(phase='complete',expires=now+1.5)
        elif event=='result_ready_without_verified_final':d.update(phase='warning',expires=now+12)
        elif event=='cancelled':d.update(phase='cancelled',record_stopped=d['record_stopped'] or now,expires=now+1.2)
        elif event in ('stream_failed_or_timed_out','failed_or_timed_out','recording_failed'):
            d.update(phase='error',expires=now+12)
        elif event=='stream_cleanup_finished' and d['phase']=='error':
            d.update(record_stopped=d['record_stopped'] or now,expires=now+12)
        elif event not in ('record_requested','recording_started','recorder_stopped','result_ready','result_ready_without_verified_final','cancelled'):
            return
        self.write()
    def heartbeat(self):
        if self.data and self.data['phase'] in ('starting','recording','processing'):self.write()

def view(data,now=None,record_alive=None,owner_alive=None):
    if not isinstance(data,dict):return None
    now=time.monotonic() if now is None else now
    try:
        phase=data['phase'];updated=float(data['updated']);started=data.get('record_started');stopped=data.get('record_stopped')
        if record_alive is None:record_alive=process_matches(data.get('recorder_pid'),data.get('recorder_identity'))
        if owner_alive is None:owner_alive=process_matches(data.get('owner_pid'),data.get('owner_identity'))
        seconds=max(0,int((float(stopped) if stopped is not None else now)-float(started))) if started is not None else 0
        clock=f'{seconds//60:02d}:{seconds%60:02d}'
        def result(color,title,detail):return {'color':color,'title':title,'detail':detail,'clock':clock,'session':str(data.get('session',''))}
        stale=now-updated>4 or not owner_alive
        if record_alive and (stale or phase not in ('recording',)):
            return result('error','录音仍在进行','状态异常，请重启输入法' if stale else '正在释放麦克风，请稍候')
        if stale and phase in ('starting','recording','processing'):
            return result('error','录音状态已中断','麦克风已关闭') if now-updated<12 else None
        expires=data.get('expires')
        if expires is not None and now>=float(expires):return None
        if phase=='starting':return result('processing','正在准备录音','等待麦克风启动')
        if phase=='recording':
            return result('recording','正在录音','实时转写 · Esc 取消') if record_alive else result('processing','正在结束录音','检查麦克风状态')
        if phase=='processing':return result('processing','正在整理文字','录音已停止 · 完成后发送' if data.get('submit_requested') else '麦克风已关闭')
        if phase=='complete':return result('recording','文字已输入','麦克风已关闭')
        if phase=='cancelled':return result('processing','已取消录音','麦克风已关闭')
        if phase=='warning':return result('error','文字已保留','最终润色未确认 · 麦克风已关闭')
        if phase=='error':return result('error','语音输入异常','麦克风已关闭，可以重新录音')
    except (TypeError,ValueError,KeyError,OverflowError):return None
    return None
