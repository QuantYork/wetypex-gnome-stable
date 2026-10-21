# WeTypeX GNOME Stable

在 GNOME Wayland 下稳定使用 **Fcitx 5 + WeTypeX（微信输入法兼容项目）**：候选框显示在正确的输入位置，并在同一段拼音输入期间保持起点。

本仓库保存 2026-10-21 在实际桌面验证过的方案，包括适配源码、测试、安装器、登录启动和卸载恢复。它是版本固定的兼容方案，仍使用 `LD_PRELOAD` 函数覆盖，**不是已经完成重构的原生 Fcitx 插件**。

## 验证环境

| 组件 | 已测试版本 |
|---|---|
| 系统 | Ubuntu 26.04.1，x86-64 |
| 桌面 | GNOME 50.1，Wayland |
| 输入框架 | Fcitx 5.1.19（Ubuntu 包 5.1.19-1） |
| 输入引擎 | WeTypeX 2.2.3.657-10 |
| GNOME 面板扩展 | Input Method Panel / Kimpanel v92 |

用户在 ChatGPT、微信、Edge、Ptyxis 终端、应用中心、文本编辑器、Firefox 中确认位置正常。其他发行版、Fcitx 版本、多显示器/缩放组合尚未全面验证。不能把“源码能编译”当成所有桌面的兼容保证。

## 解决了什么

1. **候选框随拼音移动**：在输入法处理首个按键前保存光标矩形，同一段拼音期间让候选 UI 读取保存的位置。应用和引擎仍能读取真实光标坐标。
2. **原生应用候选框偏到左上角**：使用 GNOME 的 Kimpanel 扩展绘制候选框，完成协议坐标到桌面坐标的转换。仅冻结 X11 外置窗口不足以修复这类坐标问题。
3. **旧外置窗口的移动兼容**：保留原窗口可见期间固定位置的小型适配层，作为 Classic UI 路径的兼容组件；Kimpanel 路径不依赖它。
4. **本机后端 JSON 字符兼容**：保留已验证的 Python 管道包装，将返回 JSON 规范化为 ASCII 转义；不保存输入内容。
5. **登录后可用**：安装到用户目录，由持久的 systemd 用户服务在 GNOME 图形会话启动时运行，不依赖测试窗口、工作目录或临时服务。

候选框使用 GNOME 面板样式，原 WeTypeX Classic UI 的微信主题不会直接套用。WPS 缺少行内预编辑能力时，拼音仍可能显示在候选框里；本方案不伪造应用能力。

## 安装前提

- 已安装 Fcitx 5.1.19 和 **已配置好、能正常输入的 WeTypeX**。本项目不替代 WeTypeX 的安装及微信核心初始化。
- 已有 GNOME Wayland 会话和 systemd 用户服务。
- 已安装并启用 [Input Method Panel](https://extensions.gnome.org/extension/261/kimpanel/)（`kimpanel@kde.org`）。GNOME 50 使用兼容的 v92；从扩展页面按当前 Shell 版本安装，必要时退出登录后重新登录，再确认扩展已启用。
- WeTypeX 上游：[panxuc/fcitx5-wetypex](https://github.com/panxuc/fcitx5-wetypex)。本仓库不附带其专有输入核心、词典、配对数据或账号配置。

查看版本和扩展状态：

```sh
fcitx5 --version
gnome-extensions info kimpanel@kde.org
```

请保留当前能工作的输入法环境变量。本方案继续利用 Fcitx 的 IBus 兼容前端服务 GNOME 原生应用；它并没有改成运行 IBus 输入引擎。安装器不修改 `.xinputrc`、全局 GTK/Qt 环境或词库。图形会话启动后服务通过 `-r` 接管输入法，避免把已有工具包连接方式一并改掉。

## 从源码安装（Ubuntu 已验证）

先在系统中安装构建依赖，软件包版本须与已安装的 Fcitx 一致：

```sh
sudo apt install build-essential pkg-config python3 libxcb1-dev \
  libfcitx5core-dev libfcitx5config-dev libfcitx5utils-dev

git clone https://github.com/QuantYork/wetypex-gnome-stable.git
cd wetypex-gnome-stable
python3 scripts/build.py
python3 tests/run.py
python3 scripts/install.py
```

安装最后一步会重启 Fcitx，先完成正在输入的拼音。**不要使用 sudo 运行安装器**，否则会安装到错误用户。默认不改变中英文偏好；安装后必要时切换到 WeTypeX。

只安排下次登录启动，暂不重启：

```sh
python3 scripts/install.py --no-start
```

安装器只管理以下位置：

- `~/.local/lib/wetypex-gnome-stable/`：两个适配库、版本文件、后端包装和卸载器。
- `~/.local/bin/wetypex-gnome-stable`：固定启动入口。
- `~/.local/share/applications/org.fcitx.Fcitx5.desktop`：让应用列表中的 Fcitx 5 图标重新启动同一持久服务。
- `~/.config/systemd/user/wetypex-gnome-stable.service`：图形会话服务。
- `~/.config/autostart/org.fcitx.Fcitx5.desktop`：隐藏重复的普通 Fcitx XDG 自启动入口。
- `~/.local/state/wetypex-gnome-stable/`：安装清单及所管理文件的原始备份。

已有同名文件先备份；复制库使用原子替换。不会复制、删除或上传个人词库及配对信息。服务采用 `graphical-session.target`，不启用用户 lingering，不在退出桌面后刻意常驻。不要同时维护另一个 Fcitx 常驻服务。

## 检查与测试

```sh
systemctl --user is-enabled wetypex-gnome-stable.service
systemctl --user status wetypex-gnome-stable.service
fcitx5-remote -n
journalctl --user -u wetypex-gnome-stable.service -b --no-pager
```

服务应为 `enabled` / `active`。`fcitx5-remote -n` 会按当前焦点返回输入法，可切到 WeTypeX 测试。

逐个测试：ChatGPT、微信、Edge、终端、应用中心、文本编辑器、Firefox；输入 `n`，停一秒，再输入 `ihao`，选字。观察起点、持续输入是否移动、切换窗口和重新开始输入是否重新定位。最后退出登录并重新登录再测。安装完成时的服务检查不等同于已经实测过重新登录。

自动测试使用真正的 Fcitx 核心和两个模拟 UI 调用模块，覆盖首键前保存、连续按键、真实光标不被覆盖、多上下文隔离、预编辑清空、失焦、浮窗拼音、负坐标及无效初始矩形，同时验证临时目录安装及备份恢复。可选的 X11 窗口测试会短暂创建测试窗口：

```sh
python3 tests/run.py --x11
```

默认关闭本项目的诊断坐标日志，不记录按键或输入内容。这不代表 WeTypeX 自身的联网、同步或上游数据行为由本项目控制。

## 恢复与卸载

先完成正在输入的拼音，再运行：

```sh
python3 ~/.local/lib/wetypex-gnome-stable/uninstall.py
```

卸载器停用服务，恢复所管理文件的旧版本，保留备份。安装后手动修改过的文件不会被强制覆盖，会打印保留列表。它不删除 WeTypeX、个人词库、配对数据或任何 GNOME 扩展。之后启动你希望使用的输入法，或重新登录。需要同时停用 Kimpanel 时，单独执行：

```sh
gnome-extensions disable kimpanel@kde.org
```

临时绕过本项目的定位库而保留后端 JSON 兼容（不写永久配置）：

```sh
systemctl --user stop wetypex-gnome-stable.service
WETYPE_BACKEND_LAUNCHER="$HOME/.local/lib/wetypex-gnome-stable/backend-json-compat.py" fcitx5 -rd
```

升级本项目目前采用“卸载 → 构建新版 → 重新安装”，旧备份保留。Fcitx 升级到其他版本时启动器会跳过两个版本固定的定位库，启动普通 Fcitx + 后端包装，并在服务日志提示；固定起点效果此时不保证，需要重新适配和验证，不能直接删掉版本检查。

## 全局编辑快捷键

本机另有 keyd 提供 Win / Command + A/C/V/X/Z。它与输入法框架独立，原 Ctrl 快捷键保留，配置、追加脚本及恢复方法见 [全局快捷键](docs/global-shortcuts.md)。普通输入法安装器不会自动安装这项系统级设置。

## 实时语音输入（可选）

另提供版本固定的实时语音组件：边录边回填、按最新识别结果改写前文、结束后确认润色与标点。整理期间按回车会等待最终文字，再补发一次回车；用户已确认这项行为正常。Win+C 复制不再误触 Ctrl+Win 录音。

录音状态采用独立 GNOME 顶栏项，位于左侧图标组的最右侧，显示录音计时、整理或“定稿后发送”，完成后隐藏，不覆盖正文。此顶栏显示已安装，隔离总线及显示逻辑测试通过；当前会话尚需重新登录加载新扩展并实测位置。

详见 [实时语音及历史排查](docs/voice-input.md)、[构建、组件部署与恢复](docs/streaming-voice-setup.md) 和 [顶栏状态设计](docs/voice-indicator-design.md)。普通安装器仍只安装候选框定位方案；不会自动替换系统语音插件。语音组件必须配套安装，且仅验证 Fcitx 5.1.19 / WeTypeX 2.2.3.657-10。

## 实现与限制

详见 [方案原理](docs/design.md)、[改动与验证](docs/changes.md) 和 [版本记录](CHANGELOG.md)。

输入中移动/缩放窗口、切换显示器、屏幕边缘避让和复杂候选菜单尚未全面验证。某些应用不提供有效初始光标矩形时会回退到真实坐标。不要全局设置 `LD_PRELOAD`：它只应存在于本项目启动的 Fcitx 会话。

本项目适配代码采用 MIT；Fcitx、Kimpanel 和 WeTypeX 分别遵循各自许可证。微信输入法核心、资源和服务不在本仓库分发范围内。项目不代表腾讯或相关上游背书。
