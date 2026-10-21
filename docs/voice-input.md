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
