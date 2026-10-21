# 实时语音组件的构建、部署与恢复

普通 `scripts/install.py` 只安装候选框定位层。本页是 **Fcitx 5.1.19 / fcitx5-wetypex 2.2.3.657-10 / Ubuntu 26.04 GNOME 50.1 x86-64** 的可选部署记录，不能对未知版本直接覆盖系统插件。先确保原版中文、账户联网和麦克风已正常工作。

## 构建与测试

需要匹配版本的 Fcitx、LibIME、json-c 开发头文件，以及 C++ 编译器、patch、Python 3、PipeWire 的 `pw-record`、FFmpeg Opus 编码、bubblewrap、Python GI 和 GJS。开发依赖必须与运行库版本一致；构建器拒绝未经验证的 Fcitx 版本。

准备上游干净的 `fcitx5-wetypex-2.2.3.657-10` 源码，构建器只在临时副本打补丁：

```sh
python3 scripts/build-streaming-voice.py \
  --source /path/to/fcitx5-wetypex-2.2.3.657 \
  --out "$PWD/build/streaming" --test
python3 tests/test-voice-supervisor.py
python3 tests/test-voice-stream.py
python3 tests/test-voice-indicator.py
python3 tests/test-voice-panel-service.py
gjs -m tests/test-voice-panel.js
```

如果使用解包的开发文件，可额外指定 `--headers /path/to/sysroot/usr/include`。`--test` 使用实际打补丁的 Fcitx 插件和模拟语音助手，覆盖中间文字替换、定稿后单次回车、重复回车合并、失焦取消、旧会话抑制及 Win+C 修饰键脉冲。测试不录音、不调用真实识别、不向实际应用发送回车；会话总线测试启动独立的本地总线。

## 成套部署（熟悉系统配置的用户手动操作）

先结束当前录音与拼音输入。以下示例假设定位方案的 `wetypex-gnome-stable.service` 已安装；不适用于其他启动服务。管理员权限只用于系统插件和语音入口，用户文件不要用 sudo 安装。所有路径与版本需要在目标机器再次核对。

```sh
fcitx5 --version
dpkg-query -W -f='${Version}\n' fcitx5-wetypex
# 分别必须为 5.1.19 与 2.2.3.657-10
```

用唯一目录保存原始系统文件、配置及已有用户语音组件：

```sh
voice_backup="$HOME/.local/share/wetypex-gnome-stable/backups/manual-voice-$(date +%Y%m%d-%H%M%S)"
mkdir -m 700 -p "$voice_backup"
cp /usr/lib/x86_64-linux-gnu/fcitx5/wetypex.so "$voice_backup/wetypex.so"
cp /usr/bin/fcitx5-wetypex-voice "$voice_backup/fcitx5-wetypex-voice"
cp "$HOME/.config/fcitx5/wetypex.json" "$voice_backup/wetypex.json"
voice_lib="$HOME/.local/lib/wetypex-gnome-stable"
mkdir -p "$voice_lib"
if test -d "$voice_lib"; then cp -a "$voice_lib" "$voice_backup/user-lib"; fi
printf '%s\n' "$voice_backup"
```

保留打印的备份目录。系统插件、入口、监督进程和 host 必须使用同一版；仅复制其中一个会造成重复文字或协议不匹配。

```sh
systemctl --user stop wetypex-gnome-stable.service
install -m 755 src/voice-supervisor.py src/voice-stream-launcher.py "$voice_lib/"
install -m 644 src/voice_status.py "$voice_lib/"
mkdir -p "$voice_lib/stream-support"
install -m 755 build/streaming/wetypex-engine-host "$voice_lib/stream-support/"
# 复用本机已安装上游的运行支持库，不从本仓库下载或分发：
cp -a /usr/lib/fcitx5-wetypex/wcwss_bridge.so \
  /usr/lib/fcitx5-wetypex/locale.so \
  /usr/lib/fcitx5-wetypex/libkqueue.so.0 "$voice_lib/stream-support/"
ln -sfn libkqueue.so.0 "$voice_lib/stream-support/libkqueue.so"
sudo install -m 644 build/streaming/wetypex.so /usr/lib/x86_64-linux-gnu/fcitx5/wetypex.so
sudo install -m 755 src/voice-entry.py /usr/bin/fcitx5-wetypex-voice
```

合并启用字段，保留配置中的其他项目：

```sh
python3 - <<'PY'
import json,pathlib
p=pathlib.Path.home()/'.config/fcitx5/wetypex.json'
d=json.loads(p.read_text())
d.update(voice_streaming=True,voice_smart_polish=True,voice_punctuation='添加完整标点')
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
PY
python3 scripts/voice-panel.py
systemctl --user start wetypex-gnome-stable.service
```

新本地 GNOME 扩展首次需要退出登录再登录。不是重启整台机器，也不需要退出当前账户配对。下次登录持久输入法与状态服务会继续启动；未加载顶栏扩展时保留普通通知。

## 检查

```sh
systemctl --user status wetypex-gnome-stable.service wetypex-voice-indicator.service
gnome-extensions info wetypex-voice-status@quantyork.local
fcitx5-remote -n
/usr/bin/fcitx5-wetypex-voice status
```

服务应活动、顶栏扩展应为 ACTIVE。语音由用户主动在目标应用测试：按住 Ctrl+Win 录音，松开后等待，另一次在整理期间按回车，确认只在最终文字填入后发送一次。测试时切换焦点应取消当前转录和待发送请求。不要把测试发送到重要聊天或表单。顶栏位置、多显示器、全屏隐藏顶栏仍需按实际桌面确认。

## 恢复

只恢复安装前的录音显示：

```sh
python3 scripts/voice-panel.py --restore
```

它不撤销实时语音、快捷键或输入法定位。完整恢复时先执行上述显示恢复，再停止输入法并用刚才保存的目录还原系统文件和原配置：

```sh
systemctl --user stop wetypex-gnome-stable.service
sudo install -m 644 "$voice_backup/wetypex.so" /usr/lib/x86_64-linux-gnu/fcitx5/wetypex.so
sudo install -m 755 "$voice_backup/fcitx5-wetypex-voice" /usr/bin/fcitx5-wetypex-voice
cp "$voice_backup/wetypex.json" "$HOME/.config/fcitx5/wetypex.json"
systemctl --user start wetypex-gnome-stable.service
```

仅在安装后没有升级 WeTypeX、没有修改配置时使用该直接恢复示例；否则先比较版本与差异。保留用户目录中已不被入口引用的组件不会启动录音，不要删除整个共享目录，以免损坏仍在使用的候选框适配。普通卸载器不负责上述系统文件与可选顶栏组件。

## 本次验证范围

实时改写、定稿标点、底部旧提示、Win+C 防误触和提前回车等待定稿已在本机由用户确认。顶栏新版已安装并通过独立总线、GJS 展示和语法测试，尚待首次重新登录后确认渲染位置。仓库不包含个人录音、真实识别日志、账户身份、私人词库或运行支持库；合成语音验证结果另见 `tests/voice-stream-verification.json`。
