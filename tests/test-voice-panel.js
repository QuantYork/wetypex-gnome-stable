import GLib from 'gi://GLib';
import {presentation} from '../gnome/wetypex-voice-status@quantyork.local/presentation.js';
function check(ok) { if (!ok) throw new Error('assertion failed'); }
check(presentation(null) === null);
check(presentation({}) === null);
let state = presentation({title: '正在录音', detail: '实时转写 · Esc 取消', clock: '00:12', color: 'recording'});
check(state.text === '正在录音 00:12' && state.icon === 'audio-input-microphone-symbolic');
state = presentation({title: '正在整理文字', detail: '录音已停止 · 完成后发送', clock: '00:12', color: 'processing'});
check(state.text === '定稿后发送 00:12');
state = presentation({title: '录音仍在进行', detail: '状态异常，请重启输入法', clock: '10:01', color: 'error'});
check(state.color === 'error' && state.icon === 'dialog-warning-symbolic');
const [ok, raw] = GLib.file_get_contents(GLib.build_filenamev([GLib.path_get_dirname(GLib.filename_from_uri(import.meta.url)[0]), '../gnome/wetypex-voice-status@quantyork.local/extension.js']));
check(ok);
// Parse the module body without executing Shell-only imports or touching the live panel.
new Function(new TextDecoder().decode(raw).replace(/^import .*;$/gm, '').replace('export default class', 'class'));
print('PASS: recording, queued submission, error, hidden idle and extension syntax; no live panel, microphone or network');
