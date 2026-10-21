// Input contains only the existing content-free status model, never recognized speech.
export function presentation(state) {
    if (!state || typeof state.title !== 'string' || typeof state.clock !== 'string' ||
        !['recording', 'processing', 'error'].includes(state.color))
        return null;
    const recording = state.title === '正在录音';
    const queued = state.detail?.includes('完成后发送');
    return {
        color: state.color,
        text: `${queued ? '定稿后发送' : state.title} ${state.clock}`,
        detail: `${state.title}，${state.detail ?? ''}`,
        icon: state.color === 'error' ? 'dialog-warning-symbolic' :
            recording ? 'audio-input-microphone-symbolic' :
            state.title === '文字已输入' ? 'emblem-ok-symbolic' : 'content-loading-symbolic',
    };
}
