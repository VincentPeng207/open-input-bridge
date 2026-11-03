# Open Input Bridge

**用现成的小型无线输入设备，控制电脑。** Open Input Bridge 是独立的开源桥接项目，不依赖特定品牌的自研硬件。

[English README](README.en.md) · [下载 Android APK（Releases）](https://github.com/VincentPeng207/open-input-bridge/releases) · [Android 源码](android/README.md) · [贡献指南](CONTRIBUTING.md) · [验证状态](docs/VERIFICATION.md) · [安全说明](SECURITY.md)

**重要：Windows 桥接服务默认占用 TCP 端口 `8766`。** 如果该端口已经被其他程序使用，请自行选择一个未被占用的端口，例如在项目根目录运行 `.\start-windows.cmd --port 8767`（实际命令见下方）；手机必须使用新终端输出的、包含新端口及 token 的完整地址。**程序不会自动改端口，也不会结束无关程序。** 仅对可信私人网络开放所选端口。

## 当前可用范围

首个适配链路：**LY-03 蓝牙遥控指环 → Android 手机（Open Input Bridge 前台 App 或 Chrome 前台网页）→ 私人局域网 HTTP/WebSocket → Windows Python 接收端 → 桌面快捷键**。两种手机入口共用同一 Windows 服务端与网页手势逻辑。

| 项目 | 当前状态 |
| --- | --- |
| Windows 接收端、带鉴权的 WebSocket 桥接 | 用户在 2026-11-03 验证了桥接连接与 `tap` / `SENT` 日志；其余功能仍需验收 |
| Android Chrome 前台网页 + LY-03 | 此前有实际设备成功记录；本次 Chrome 路径未单独记录完整复验 |
| 中键单击触发可配置快捷键 | 历史实测成功；需设置目标软件热键 |
| 中键快速双击发送 Enter | 已有实现与自动化测试；实际识别受设备输入事件限制 |
| 上下操作映射方向键 | 历史单击实测可用，默认每次重复 8 步；方向感和手感需复验 |
| Android WebView App | **源码与 Release 调试 APK 已提供；用户确认从 Release 安装后正常可用，双击、休眠与长时间稳定性仍待系统验收** |
| iOS、macOS、Linux 接收端、其他设备 | 未支持/未验证 |

**验证说明：** 2026-11-03 用户报告 Windows 接收端输出了 `tap -> ctrl+win (SENT)`，并确认下载 Release Android App 后可正常使用。这是用户实际反馈，未代替完整的双击、锁屏、休眠与长时间稳定性验收。

## 开始之前

- Windows 10/11 电脑：安装 Python **3.10+**（带 Windows 的 `py` 启动器）。PowerShell 运行 `py -3 --version` 确认安装。
- Android 手机：通过系统蓝牙设置与 **LY-03** 正常配对。可选择 Open Input Bridge **Android App（Android 14+）**，或使用 **Chrome 浏览器**（已具有历史实测记录）。
- 手机与电脑接入**同一可信任私人 Wi-Fi/局域网**，相互可达；电脑防火墙仅对**私人网络**放行 Python 的入站连接。
- 将这个仓库下载 ZIP 并解压，或用 Git 克隆；Windows 端无需第三方 Python 包或专用驱动。选择 App 时需要安装 Android 调试 APK，选择 Chrome 时无需安装 App。
- **运行期间手机必须保持解锁、屏幕常亮、不进入锁屏状态，桥接 App 或 Chrome 桥接页面必须保持在前台（顶层）、可见并处于活动状态。** 后台、锁屏均不支持转发。Android App 会在桥接界面请求屏幕常亮，但请确认系统没有将其暂停。
- **LY-03 会自动休眠。** 长时间未使用、按钮无响应时，可**长按中键约 2 秒，尝试唤醒并恢复蓝牙连接**；确认手机蓝牙重新连接后再单击。不同设备批次的唤醒成功率仍需验收。

## 1. Windows：先进行无键盘输入的安全测试


**修改端口示例（默认 8766 被占用时）：**

```powershell
.\start-windows.cmd --port 8767 --dry-run
```

使用别的端口后，手机地址也必须是 `http://<电脑局域网IP>:8767/?token=...`（以程序实际打印的完整地址为准）。

在解压后的项目根目录打开 PowerShell：

```powershell
py -3 .\windows\ly03_voice_bridge_ws_v1.py --dry-run --hotkey "ctrl+win" --copy-url
```

此模式不向 Windows 注入任何按键。终端默认**只打印一个推荐的私人局域网地址**，例如 `Open on PHONE: http://192.168.x.x:8766/?token=...`。请完整复制包含端口与 token 的 URL，供 Android App 或 Chrome 使用。如电脑连接多个网络，可能还存在 `172.16–31.x.x` 地址（例如 VPN/虚拟网卡）。若推荐地址无法被手机访问，可运行 `py -3 .\windows\ly03_voice_bridge_ws_v1.py --dry-run --show-all-addresses` 查看所有网卡候选地址并检查实际网络连接。**显示推荐地址不等于已经验证手机可访问**。界面显示“在线”只说明 WebSocket 已连接。Windows 防火墙仅允许私人网络。

Windows 控制台应在操作桥接界面的“测试：单击组合键”按钮后显示类似 `[BRIDGE] tap -> ctrl+win (DRY-RUN)`；快速双击或使用“测试：双击 Enter”按钮则显示 `double -> enter (DRY-RUN)`。随后佩戴并配对 LY-03，**保持手机解锁、亮屏、桥接程序在前台活动状态**，在页面主操作区域按指环中键，检查相应日志。方向操作应出现 `up` / `down` 日志。界面测试按钮只能验证连接与映射，不能代替物理按键识别测试。

`--copy-url` 也会将完整网址复制到 Windows 剪贴板；若显示复制失败，可手动复制终端地址。请勿公开或截图传播带 token 的完整地址。

## 2. 选择手机桥接端

**Android App 源码完整公开在本仓库**，不是只有编译后的 APK：可直接审查 [Java 主程序](android/app/src/main/java/org/openinputbridge/android/MainActivity.java)、[AndroidManifest.xml](android/app/src/main/AndroidManifest.xml)、[Android 构建配置](android/app/build.gradle)。App 加载的网页 HTML/JavaScript 也以源码形式保存在 [Windows 接收端的 `PAGE` 字符串](windows/ly03_voice_bridge_ws_v1.py) 中。使用者可以阅读、修改代码并自行编译；APK 只是可选的 CI 测试产物，仓库不提交 APK 二进制。详情见 [Android 源码与编译指南](android/README.md)。

**方式 A：Android App（源码和调试 APK 已提供，用户已确认可安装使用；高级场景待复验）**

1. 手机需要 **Android 14 或更新版本**。优先前往 **[GitHub Releases 下载 Android APK](https://github.com/VincentPeng207/open-input-bridge/releases)**，选择 `android-v0.1.0-preview.1` 等最新的 Android 预发布版本，下载 `Open-Input-Bridge-Android-...-debug.apk` 并安装；同一 Release 附有 SHA256 校验文件和对应源码快照。也可以到 [Android 构建工作流](https://github.com/VincentPeng207/open-input-bridge/actions/workflows/android.yml) 下载短期保留的测试工件。**这是调试签名的测试版；已有用户实际安装使用反馈，但尚未完成完整真机测试矩阵，不是应用商店正式版。**
2. 在 Android 系统蓝牙设置中配对 LY-03；启动 **Open Input Bridge**，将 Windows 终端刚显示的完整 `http://.../?token=...` 地址粘贴到设置页，点击“连接并进入桥接”。
3. **让 App 始终处于前台/顶层活动状态、手机解锁并保持屏幕常亮。** 桥接页会请求保持屏幕常亮；离开 App、切换应用或锁屏时不会继续转发，返回后需要恢复连接。它不是后台服务。
4. 先用界面内测试按钮验证网络，再用指环进行 `--dry-run` 试验。用户已确认 Release App 可以使用；新设备/机型仍需验证 WebView 对实际 LY-03 按键的识别情况。

**方式 B：Android Chrome（历史已经跑通的浏览器路径）**

Android 手机蓝牙配对 LY-03 后，用 Chrome 打开 Windows 终端输出的完整 LAN URL；保持手机**不锁屏、Chrome 桥接网页始终位于前台（顶层）**，然后用界面按钮与指环逐项测试。无需安装 App。若 App 真机识别不理想，可用此方式作为对照。

无论哪种方式，**页面显示“在线”只表示手机与 Windows 接收端相连，并不保证 LY-03 的蓝牙连接状态**。指环休眠后可长按中键约 2 秒尝试重新连接（等待 Android 蓝牙状态恢复后再操作）。

## 3. Windows：执行真实快捷键

用 `Ctrl+C` 停止测试服务，再运行：

```powershell
py -3 .\windows\ly03_voice_bridge_ws_v1.py --hotkey "ctrl+win" --copy-url
```

**每次重启都会生成新 token**。必须在 Android App 的设置页更新地址，或在手机 Chrome 重新打开本次运行新打印的 URL。让 Windows 目标输入框处于焦点状态；中键单击在约 300ms 判定后发送默认的 **Win + Ctrl（`Ctrl+Win`）**，快速双击发送 **Enter**（默认固定映射，不先发送单击）。

**语音输入法需要单独配置：** 在微信、豆包或你使用的其他语音输入软件中，把“开始/停止语音输入”热键设置成 **Win + Ctrl**，和桥接脚本的默认值一致。**Win + Ctrl 不是 Windows 内置通用语音快捷键。** 如果你在语音输入法中改为其他组合（例如 `Ctrl+Shift+V`），启动脚本也必须同步改成 `--hotkey "ctrl+shift+v"`。相隔数秒的两次普通单击可以分别启停语音；**快速双击**是另一种手势，发出 Enter，其实际效果由输入法/聊天软件决定。

**不依赖语音软件的可见验证：** 先在记事本输入一些文字，把上面命令中的热键换为 `--hotkey "ctrl+a"`，聚焦记事本后单击指环应选中全部文字；快速双击应发送 Enter（效果随焦点/选区而异）。确认硬件链路成功后，再换回实际语音快捷键。

**推荐使用自动重启启动器：** 项目根目录的 `start-windows.cmd` 默认使用 `--hotkey "ctrl+win" --copy-url`。在 PowerShell 中执行 `.\start-windows.cmd --dry-run` 可安全测试，或执行 `.\start-windows.cmd --hotkey "ctrl+a"` 指定热键。启动器会检查当前端口：**只在确认旧进程属于同一份仓库中的桥接脚本后，才自动关闭旧进程并启动新服务**；如果其他进程占用了端口，会报错而不会结束它。直接运行 `py -3 .\windows\ly03_voice_bridge_ws_v1.py` 则不执行自动替换。每次重启都需要在手机 App 或 Chrome 打开**新生成的 Token URL**。

## 操作与参数

| 手势 / 命令 | Windows 动作 |
| --- | --- |
| 中键单击 / `tap` | `--hotkey` 指定组合键（单击判定等待默认 300ms） |
| 中键快速双击 / `double` | `Enter`，不应先触发单击 |
| 向上 / `up` | `ArrowUp` 默认重复 8 次 |
| 向下 / `down` | `ArrowDown` 默认重复 8 次 |

通过 `--scroll-steps 4` 调整方向键次数（1–16），`--swipes pages` 改为 PageUp/PageDown，`--swipes ignore` 禁用上下动作，`--port 8767` 指定端口，`--bind 127.0.0.1` 只监听本机、用于安全本地测试。**网页目前不发送方向双击**；接收端仍识别历史的 `up_double/down_double` 消息以保留协议兼容。

断线后按键**直接丢弃、不排队、不重发**，防止恢复联网后突然产生 Enter；界面显示连接状态、心跳与 ACK。**手机锁屏、桥接程序转后台、失去前台焦点时不支持控制；Windows 睡眠或 LY-03 自身休眠也会中断操作。** 指环休眠后可先长按中键约 2 秒尝试唤醒并恢复手机蓝牙连接，再试一次短按；网页显示“在线”只反映手机与 Windows 的 WebSocket 状态，并不能保证 LY-03 已连接。

## 故障排查

- **手机打不开网页**：确认电脑脚本正在运行且端口号与手机 URL 一致；两个设备在同一可互访局域网；先使用终端推荐的 IPv4 地址，如果无法访问，加入 `--show-all-addresses` 查看候选地址并检查网卡。不要把 `127.0.0.1` 当成手机要访问的电脑地址。确认防火墙只对私人网络放行，注意公共 Wi-Fi 的客户端隔离。
- **403 / unauthorized / 持续断开**：使用**最新启动**显示的完整 `?token=...` URL；不是旧书签。必须用 `http://` 打开网页，浏览器会自动连接同源 `ws://`。
- **页面在线，但指环按键没有日志**：在 Android 蓝牙设置确认 LY-03 已连接；**不要锁屏，确保 Android App 或 Chrome 页面处于顶层活动状态**；试页面内“测试”按钮区分网络与物理事件。若指环休眠，**长按中键约 2 秒尝试唤醒/重新连接**，确认蓝牙状态后再短按；不同固件可能需重复操作。
- **有 `DRY-RUN` 日志但电脑不动作**：停止服务后去掉 `--dry-run`，再次用新 URL 连接；检查目标窗口是否获得焦点，以及语音输入法启停热键是否与 `--hotkey` 一致（默认 `ctrl+win`）。
- **默认端口 8766 已被占用**：使用 `start-windows.cmd` 可安全替换**本仓库同一路径的旧桥接进程**；如果是其他程序占用，请自行选择未占用的端口，例如 `.\start-windows.cmd --port 8767`（或直接调用 Python 时添加 `--port 8767`），并使用终端打印的新 URL。启动器不会强制结束不匹配的程序。
- **Windows 日志显示动作 SENT 但无响应**：先用记事本 `ctrl+a` 排查。管理员权限窗口、某些输入法或快捷键冲突可能拦截模拟输入。

## 测试和贡献

本版接收端只用 Python 标准库。可选安装 Node.js 18+ 运行浏览器事件测试：

```powershell
py -3 -B -m unittest discover -s windows -p "test_*.py" -v
node .\windows\test_directional_classifier.js
```

若未安装 Node.js，Python 中两项 JS 测试会跳过，并不代表 JS 部分已经通过。首次 GitHub Actions CI 已在 Ubuntu 与 Windows 上通过自动化回归（[运行记录](https://github.com/VincentPeng207/open-input-bridge/actions/runs/41583966770)）；**CI 不等于 LY-03 真机验证**。请参考 [验证矩阵](docs/VERIFICATION.md) 留下设备/浏览器/Windows 版本及测试记录。

Android App 源码、打包方式及验收事项参见 [android/README.md](android/README.md)。后续设备适配应尽量以独立小模块或示例加入，明确设备事件来源与已验证系统；不要为未来平台提前重构可用核心。具体见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 安全与许可证

仅在可信任私人 LAN 中使用：HTTP/WS **没有 TLS 加密**，启动时生成随机临时 token，服务端仅接受固定白名单命令，不接受远程任意键值。不要向公网开放 8766 端口，不要共享 token URL；此工具可向当前焦点程序注入键盘操作。详见 [SECURITY.md](SECURITY.md)。

代码采用 [MIT License](LICENSE)。第三方设备商标归各权利人所有；本项目与 LY-03 厂商没有从属或官方支持关系。
