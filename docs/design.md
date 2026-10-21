# 方案原理

## 三层职责

```text
应用 / GTK / Qt / GNOME 原生输入协议
                  │
             Fcitx 5 输入上下文
                  │
      WeTypeX 插件 → JSON 管道包装 → 已安装的 WeTypeX 后端
                  │
       候选、行内拼音、真实光标矩形
                  │
          首键前位置保存层
                  │
  Kimpanel 协议 → GNOME Input Method Panel → 屏幕上的候选框
```

这不是“Fcitx 套着一个正在运行的 IBus 引擎”。Fcitx 实现 IBus 兼容前端，使 GNOME 和部分工具包可以连接；输入引擎仍然是 WeTypeX。

## 两类不同问题

应用会随着行内拼音增加上报新的光标位置。冻结第一次可见窗口，可能已经晚于第一个字母完成排版。因此在 `InputContextKeyEvent` 的 `PreInputMethod` 阶段、当前没有拼音时保存光标矩形；候选 UI 读取矩形时返回保存值。直接读取真实光标的前端和引擎不被替换。预编辑清空、失焦、重置、切换输入法和销毁上下文时释放该状态。

另一类问题是窗口局部坐标、协议坐标、桌面坐标和缩放并不相同。单纯固定外部 X11 窗口可能把错误位置固定下来。GNOME 扩展能使用 Mutter 的 `protocol_to_stage_rect`、焦点窗口和缩放信息，完成候选框定位。本机用户测试证明使用 Kimpanel 后，多种原生应用的左上偏移消失。

## 当前实现

`src/prekey-anchor.cpp` 只覆盖 Fcitx 5.1.19 的两个导出函数：

- `Instance::exec()`：在进入主循环前注册正式事件监听器，并在退出时清理状态。
- `InputContext::cursorRect()`：只向 `libclassicui.so` 与 `libkimpanel.so` 的调用返回保存位置；其他调用返回原始结果。

注册事件监听器是有意选择的：本机 Fcitx 发行包对核心内部函数采用本地绑定，单纯拦截 `Instance::postEvent` 无法可靠收到真实输入事件。

`src/window-anchor.c` 识别 `Fcitx5 Input Window` 的 WM_NAME，只在该窗口已映射且可见时固定 X/Y，保持宽高更新，隐藏和销毁后清除。保留它是为了与已验证的 Classic UI 路径一致；Kimpanel 是 GNOME 会话的主要显示方式。

`backend-json-compat.py` 只将返回 JSON 重新序列化为 ASCII 转义，并透传请求。它不记录输入内容、不实现账户登录、不改词库，也不替代 WeTypeX 后端。

## 持久化边界

本次将工作目录和临时 `systemd-run` 服务替换成 `~/.local` 下固定安装及 `wetypex-gnome-stable.service`。启用状态由 systemd 保存，图形会话启动时自动运行。原 `.xinputrc` 和工具包环境变量保留，以减少这次变化的范围；安装的用户 XDG override 避免普通 Fcitx 桌面自启动重复启动。

本方案并没有消除函数覆盖的 ABI 风险。兼容性只声明为 Fcitx 5.1.19，升级后自动跳过定位覆盖。下一阶段可把保存位置逻辑合入 Fcitx/Kimpanel 源码，移除 `LD_PRELOAD`；本版本没有宣称已经完成那项重构。

## 参考

- [Fcitx 在 Wayland 下的集成说明](https://fcitx-im.org/wiki/Using_Fcitx_5_on_Wayland/en)
- [Kimpanel 协议](https://fcitx-im.org/wiki/Kimpanel)
- [GNOME Input Method Panel](https://extensions.gnome.org/extension/261/kimpanel/)
- [Kimpanel 扩展源码](https://github.com/wengxt/gnome-shell-extension-kimpanel)
- [Fcitx 5.1.19 源码](https://github.com/fcitx/fcitx5/tree/5.1.19)
- [WeTypeX 上游](https://github.com/panxuc/fcitx5-wetypex)
