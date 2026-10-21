#!/usr/bin/python3
"""Optional system helper patch: status notifications and content-free timing."""
import datetime,os,pathlib,shutil,tempfile,sys


def render(s):
    if '# wetypex-gnome voice feedback v1' in s:return s
    before='log="$state/voice/last-record.log"\n'
    helper='''log="$state/voice/last-record.log"
# wetypex-gnome voice feedback v1
latency="$state/voice/latency.log"
notification="$state/voice/notification-id"
phase=initializing
stamp() { date +%s%3N; }
mark() { printf '%s %s\\n' "$(stamp)" "$1" >> "$latency"; }
feedback() {
    command -v notify-send >/dev/null 2>&1 || return 0
    previous=0
    if [ -r "$notification" ]; then previous="$(cat "$notification")"; fi
    case "$previous" in *[!0-9]*|'') previous=0;; esac
    if id="$(timeout 2 notify-send --app-name=WeTypeX --icon=audio-input-microphone \\
        --replace-id="$previous" --print-id --expire-time=4000 "语音输入" "$1" 2>/dev/null)"; then
        case "$id" in *[!0-9]*|'') :;; *) printf '%s\\n' "$id" > "$notification";; esac
    fi
    return 0
}
finish() {
    result=$?
    trap - EXIT
    if [ "$result" -ne 0 ]; then
        mark "failed_$phase"
        feedback "语音输入失败，请重试；诊断信息已保存在本机"
    fi
    exit "$result"
}
trap finish EXIT
recorder_alive() {
    kill -0 "$recorder" 2>/dev/null || return 1
    if [ -r "/proc/$recorder/stat" ]; then
        process_state="$(awk '{print $3}' "/proc/$recorder/stat" 2>/dev/null || true)"
        [ "$process_state" != Z ] || return 1
    fi
    return 0
}
'''
    replacements=[(before,helper),
      ('    rm -f "$wav" "$opus"','    phase=recording\n    : > "$latency"\n    mark record_requested\n    rm -f "$wav" "$opus"'),
      ('    chmod 600 "$control" "$log"','    chmod 600 "$control" "$log"\n    mark recorder_started\n    feedback "正在录音；按住说话模式松开后结束，持续录音模式按任意普通键结束"'),
      ('    kill -INT "$recorder" 2>/dev/null || true','    phase=stopping\n    mark stop_requested\n    feedback "录音结束，正在识别…"\n    kill -INT "$recorder" 2>/dev/null || true'),
      ('while kill -0 "$recorder" 2>/dev/null &&','while recorder_alive &&'),
      ('if kill -0 "$recorder" 2>/dev/null; then','if recorder_alive; then'),
      ('    test -s "$wav" || exit 1','    mark recorder_stopped\n    test -s "$wav" || exit 1\n    phase=encoding'),
      ('    output=\n    attempt=0','    mark encoding_finished\n    phase=recognizing\n    output=\n    attempt=0'),
      ('      if output="$(/usr/bin/fcitx5-wetypex-account voice-file "$opus")"; then','      mark "recognition_attempt_$attempt"\n      if output="$(/usr/bin/fcitx5-wetypex-account voice-file "$opus")"; then'),
      ('    result="$state/voice/result.json"','    mark recognition_finished\n    phase=delivering\n    result="$state/voice/result.json"'),
      ('\nPY\n    ;;','\nPY\n    mark result_ready\n    phase=done\n    feedback "识别完成，已准备回填；请保持输入框焦点"\n    ;;')]
    for old,new in replacements:
        if s.count(old)!=1:raise ValueError('Unknown voice helper layout; no changes: '+old.splitlines()[0])
        s=s.replace(old,new,1)
    return s


def main():
    p=pathlib.Path('/usr/bin/fcitx5-wetypex-voice')
    if p.is_symlink() or not p.is_file():raise SystemExit('Unexpected voice helper path.')
    old=p.read_text();new=render(old)
    if '--dry-run' in sys.argv:
        print('Known helper; status notifications and timing patch can be applied.' if old!=new else 'Already applied.')
        return
    if os.geteuid()!=0:raise SystemExit('Run through pkexec for administrator authorization.')
    if old==new:print('Already applied.');return
    directory=pathlib.Path('/var/backups/wetypex-gnome-stable');directory.mkdir(mode=0o755,parents=True,exist_ok=True)
    backup=directory/('voice-before-feedback-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sh')
    shutil.copy2(p,backup)
    fd,temp=tempfile.mkstemp(prefix='.wetypex-voice-',dir=p.parent)
    try:
        with os.fdopen(fd,'w') as f:f.write(new)
        os.chmod(temp,p.stat().st_mode & 0o777);os.chown(temp,0,0);os.replace(temp,p)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    print('Installed voice status notifications and timing; backup:',backup)

if __name__=='__main__':main()
