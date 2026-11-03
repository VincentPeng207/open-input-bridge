# Security / 安全说明

[English](#english-security-guide) | [中文](#中文安全指南)

## 中文安全指南

### 1. 项目安全边界

Open Input Bridge 把手机端接收到的输入事件，经局域网传给 Windows 接收程序，再模拟键盘按键。发送目标是**当时拥有键盘焦点的 Windows 程序**，因此错误的热键、误触或未经授权的连接都可能影响正在编辑的内容、聊天窗口或其他应用。

**本项目仅适用于可信任的私人局域网，不是互联网远程控制服务。** 初始版本没有用户账号、TLS/HTTPS、设备身份验证、端到端加密或完整的访问控制系统，也不能防止同一网络中的恶意主机窥探明文流量。

### 2. 网络与防火墙

- 电脑与 Android 手机应接入同一个可信任、互相可达的私人 Wi-Fi/局域网；不要在公共 Wi-Fi、共享访客网络或不可信企业网络上使用。
- 默认 Windows 服务监听 `0.0.0.0:8766`，便于手机连接。**只允许 Windows 防火墙的私人网络配置文件访问**，不要对公共网络放行。
- **不要**配置路由器端口转发、UPnP 自动暴露、反向代理或公网映射，不要把端口 8766 公开到互联网。
- 单机测试时使用 `--bind 127.0.0.1`；此时手机不能访问电脑是正常现象。
- HTTP 和 WebSocket 使用明文 `http://`、`ws://`。同一网络中具有监听能力的人可能获得页面地址、token 和指令内容。随机 token **不能替代网络隔离或加密**。

### 3. Token 与授权

- Windows 接收程序**每次启动**使用安全随机数生成一个新的临时 token；访问页面与建立 WebSocket 控制连接都要求该 token。
- 页面地址形如 `http://<电脑局域网IP>:8766/?token=...`，**整个 URL 都属于敏感凭据**。不要粘贴到公开 Issue、聊天截图、日志附件、演示视频或公开文档。
- `--copy-url` 会把完整 URL 放入 Windows 剪贴板；复制到 Android 后建议清理剪贴板，不要同步给不可信设备。
- Android App 将 URL 保存在应用私有偏好设置内，关闭 Android 系统备份；它不是密码保险箱。共享手机、已 root 手机、恶意软件或本机调试都可能造成泄露；可通过清除应用数据移除保存的 URL。
- 重启 Windows 接收程序后旧 token 自动失效；App/浏览器必须输入**新的完整 URL**。怀疑泄露时，应停止并重启 Windows 接收程序，让旧 token 失效。
- 服务端检查浏览器 WebSocket 的 Origin，并限制允许执行的命令；这些检查降低误用风险，但不应视为对恶意局域网的充分保护。

### 4. 键盘操作与失联处理

- Windows 仅执行预设的 `--hotkey`、Enter、方向键和翻页键；不会根据远端传入的任意字符串执行系统命令或任意键码。
- 中键单击默认发送 `Ctrl+Win`（应在语音输入软件中设置为启停热键），快速双击发送 Enter。请注意 Enter 可能发送聊天消息，也可能只是结束语音识别，取决于当前软件的状态。
- **先用 `--dry-run` 观察日志，再执行真实快捷键。** 真实执行前确认 Windows 焦点落在预期应用，不要在密码输入框、敏感业务操作或高风险界面中试验。
- 断线期间的事件会被丢弃；重连后**不会补发**旧按键。收到 ACK 只表示服务器接收/处理了指令，不保证目标应用实际执行了预期动作。
- 手机锁屏、切换到后台、Android App 失去前台焦点时，不支持继续控制电脑。指环自身休眠可能导致首次动作丢失。

### 5. Android App 风险

- 目前 Android App 是**前台 WebView 壳应用**，使用网页事件逻辑；它不是后台服务，也不请求无障碍服务权限。它请求联网权限，并允许连接到受限的私人局域网 HTTP 地址。
- App 校验输入的 URL 只使用私人 IPv4 地址、有效端口和 token；不能保证该局域网服务器就是预期的 Windows 电脑。
- 为了加载私人局域网服务，Android App 允许明文网络流量。**不得输入外部公开网址或把它当成通用浏览器。**
- GitHub Releases 提供的 APK 为**已自动使用调试密钥签名的测试构建**，并非固定发布证书签名的正式版，未经过安全审计或应用商店审核。建议从本项目 [Releases](https://github.com/VincentPeng207/open-input-bridge/releases) 下载并核对 SHA256；安装时留意 Android 系统的未知来源提示。后续使用固定密钥签名无需向证书机构付费，但密钥须由维护者安全保管。
- 目前不包含广告、遥测或第三方统计 SDK；不能据此认为 Android 系统、浏览器或局域网本身没有数据泄露风险。

### 6. 漏洞报告与发布前检查

发现潜在漏洞时，请勿在公开 Issue 中附上可利用的漏洞细节、个人 IP 地址、完整 token URL 或敏感日志。优先使用仓库的 **GitHub 私密安全报告（Private vulnerability reporting，如已启用）**，或其他已由维护者公开说明的私下联系渠道。没有可用私密渠道时，先用不包含利用细节的方式请求建立联系。

转为 Public 前应重新扫描**当前文件与完整 Git 历史**，核对源码许可权、生成包和 CI 权限，并完成 Android 真机安装与按键验收。仅从最新分支删除文件，**不能让旧 Git 提交历史里的内容自动消失**。

## English security guide

### Trust model

Open Input Bridge forwards phone input events over a LAN to a Windows process that injects keyboard events into the **currently focused application**. It is **not an Internet-facing remote control system**. The initial implementation has no TLS, end-to-end encryption, user accounts or protection from a malicious host on the same network.

### Network

Use only a mutually reachable, **trusted private Wi-Fi/LAN**. The receiver listens on `0.0.0.0:8766` by default; allow inbound traffic only on the Windows **Private** firewall profile. Do not use port forwarding, UPnP exposure or public proxies. Use `--bind 127.0.0.1` for local-only testing. HTTP and WS are plaintext: anyone able to observe the LAN traffic may capture the URL token and commands.

### Authorization and privacy

A fresh random token is generated on each Windows receiver launch and required for HTTP page access and WebSocket setup. Treat the **full token-bearing URL as a secret**: never share it in screenshots, issue reports or recordings. `--copy-url` stores it in the Windows clipboard; clear it after transfer as appropriate. The Android App stores the URL in app-private preferences with Android backup disabled, but a compromised/rooted device may still leak it. Restart the receiver to invalidate an exposed token. Server-side Origin checking and a strict action allowlist are safeguards, **not substitutes for encryption**.

### Operational precautions

Start with `--dry-run`. Before using live key injection, focus the intended Windows window. The default middle single-click sends Ctrl+Win (configure the same activation/deactivation shortcut in your voice-input application); a quick middle double-click sends Enter. Depending on the active app, Enter could send a message or simply finalize dictation. Offline actions are dropped and **never replayed**. An ACK does not guarantee the target app visibly performed the action. Lock-screen and background operation are not supported.

### Android App

The Android build is a foreground-only WebView client; it does not require Accessibility privileges or run a background bridge service. It needs network access and enables cleartext LAN HTTP for the local bridge. Its validated address format does not prove the LAN endpoint is trustworthy. GitHub Releases distributes a **debug-signed APK**, not a fixed-key, audited store release. Download from the project Releases page and verify SHA256; inspect Android's sideloading warnings. A privately generated signing key requires no certificate purchase, but must be secured for updates. There are no included advertising, telemetry or analytics SDKs.

### Responsible disclosure

Do not publish exploitable details or tokens in a public issue. Use GitHub's private vulnerability reporting where enabled, or request a private contact channel without exposing exploit details. Before making the repository public, audit **all reachable Git history**, license provenance, artifacts and CI permissions; deleting a file from the latest branch does not erase historical commits.
