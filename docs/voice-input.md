# 语音录音、识别成功但没有回填

本机排查发现：快捷键已触发、PipeWire 录音与 Opus 编码正常，识别返回成功，但含原始 UTF-8 中文的 `voice-inbox.json` 没有被当前适配层接收。使用不存在的会话编号分别测试原始 UTF-8 与等价 ASCII 转义 JSON：前者留在收件文件，后者被接收。未向任何应用投递测试文字。

最小兼容修复是将 `/usr/bin/fcitx5-wetypex-voice` 最后生成收件文件的 Python `json.dumps` 从 `ensure_ascii=False` 改为 `ensure_ascii=True`。中文内容不变，快捷键和麦克风设置不变。不把它解释为上游所有版本均有相同问题。

遇到相同症状才手动应用，需要管理员授权：

```sh
pkexec /usr/bin/python3 "$PWD/scripts/fix-voice-json.py"
```

脚本仅接受已知的唯一目标行，先把原脚本备份到 `/var/backups/wetypex-gnome-stable/`，再原子替换；遇到未知版本拒绝修改。正常安装器不会自动执行此系统级修复。WeTypeX 软件包更新可能覆盖它，更新后应先确认是否仍需该修复。

恢复时选择脚本打印的确切备份文件，使用管理员权限复制回 `/usr/bin/fcitx5-wetypex-voice`。这项系统脚本修复不属于用户目录卸载器管理的文件，卸载用户层方案不会自动撤销它。

验证：已用安装后的真实脚本处理合成识别结果，确认 JSON 等价且能被 Fcitx 接收。尚需用户在实际输入框中按住 Ctrl+Win 说话、松开并保持焦点等待，验证真实端到端回填。语音识别本身会使用 WeTypeX 上游联网功能，本项目不会额外上传录音或识别内容。

## 录音没有提示或感觉等待很久

当前上游 helper 采用录完后编码、再上传识别的流程，不是边说边转写。本项目提供可选状态提示和不含内容的阶段耗时补丁：

```sh
python3 scripts/improve-voice-feedback.py --dry-run
python3 tests/test-voice-feedback.py
pkexec /usr/bin/python3 "$PWD/scripts/improve-voice-feedback.py"
```

补丁显示“正在录音”“正在识别”“识别完成、已准备回填”或失败通知，复用通知编号，不将录音内容、识别文本或账号信息放入通知。系统勿扰或通知设置可能影响可见性。完成提示意味着收件文件已写入，不保证焦点已切换的应用仍会接收结果。

同时在私有 `state/voice/latency.log` 中记录毫秒时间戳和阶段名：`record_requested`、`recorder_started`、`stop_requested`、`recorder_stopped`、`encoding_finished`、`recognition_attempt_N`、`recognition_finished`、`result_ready`。不写入录音或转写内容，每次新录音重置该耗时文件。保留原重试策略和音频编码参数，不为追求速度降低音质或关闭文字整理。

停止等待会把僵尸录音进程视为已经结束，避免在音频已关闭后仍因 `kill -0` 返回成功而空等。此改动不消除联网识别耗时，也没有实现流式识别。

应用前先备份到 `/var/backups/wetypex-gnome-stable/voice-before-feedback-<时间>.sh`。若要恢复，使用打印的确切文件覆盖 `/usr/bin/fcitx5-wetypex-voice`。这是独立系统级补丁，不由用户目录卸载器自动恢复，WeTypeX 升级可能覆盖它。脚本已带同一标记时重复执行不改动；未知布局拒绝修改。

验证使用模拟录音器、编码器、账户命令和通知工具，覆盖开始/识别/完成/失败、ASCII 收件格式和无内容耗时日志，不启动真实录音或访问网络。实际延迟改善仍需在用户下一次语音后按阶段记录确认。
