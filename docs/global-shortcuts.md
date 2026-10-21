# 全局 Win / Command 编辑快捷键

本机使用 keyd 在全局把 Win / Command 组合映射到应用常用的 Ctrl 组合。这是独立于 Fcitx、IBus、Rime 和 WeTypeX 的键盘层配置。

| 实际按键 | 发送给应用 | 功能 |
|---|---|---|
| Win / Command + A | Ctrl + A | 全选 |
| Win / Command + C | Ctrl + C | 复制 |
| Win / Command + V | Ctrl + V | 粘贴 |
| Win / Command + X | Ctrl + X | 剪切（2026-10-21 新增） |
| Win / Command + Z | Ctrl + Z | 撤销（2026-10-21 新增） |

原 Ctrl 组合仍然保留。`Ctrl + Win + A` 保持原样，用于此前配置的微信截图快捷键；本次未增加 Shift+Win+Z 重做等其他映射。具体编辑动作由应用决定，例如终端的 Ctrl+Z 可能表示挂起前台进程。

配置位置为 `/etc/keyd/win-copy-paste.conf`，参考内容在 [config/win-copy-paste.conf](../config/win-copy-paste.conf)。`[ids] *` 延续本机原设置，匹配键盘设备；它不是每个应用单独设置。

## 已有 A/C/V 映射时追加 X/Z

先预览，再通过管理员授权执行：

```sh
python3 scripts/extend-global-shortcuts.py --dry-run
pkexec /usr/bin/python3 "$PWD/scripts/extend-global-shortcuts.py"
```

脚本针对本机 Ubuntu 的 `/usr/bin/keyd.rvaiya`；其他发行版可能使用 `keyd`，应先核实可执行文件及服务名称。该脚本不负责首次安装 keyd，也不替换未知的已有 X/Z 映射。普通输入法安装器不会自动修改全局快捷键。

执行前先备份旧配置到 `/var/backups/wetypex-gnome-stable/keyd-before-cut-undo-<时间>.conf`，只添加 `[meta]` 下缺失的 X/Z 两项，然后热重载。重载失败则恢复旧文件。无需重新登录。

## 恢复

使用执行时打印的确切备份路径，将旧配置复制回 `/etc/keyd/win-copy-paste.conf`，再重载 keyd。本次备份文件属于系统级独立改动，不由输入法用户目录卸载器自动恢复。

```sh
sudo cp /var/backups/wetypex-gnome-stable/keyd-before-cut-undo-<时间>.conf /etc/keyd/win-copy-paste.conf
sudo /usr/bin/keyd.rvaiya reload
```

## 验证记录

- 自动测试验证：只添加 X/Z，保留 A/C/V 和截图例外，重复执行不重复添加，遇到冲突拒绝覆盖。
- 本机 keyd 已成功重新解析配置，服务为 active。
- 尚需在实际编辑器中测试 Win+X 剪切、Win+Z 撤销，未模拟用户按键或改动用户文档。
