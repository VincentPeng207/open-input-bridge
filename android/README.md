# Open Input Bridge — Android 前台 App

[English instructions](../README.en.md#android-app-build-and-install) · [中文快速开始](../README.md)

这是可编译的 **Android WebView App 源码**，复用 Windows 接收端提供的同一网页及手势处理逻辑。不需要 Android 原生蓝牙监听器、无障碍权限或后台服务；先在手机蓝牙设置中正常连接 LY-03。

## Android App 原始源码与审查

**仓库同时提供未打包的全部 App 源代码，不必依赖现成 APK。** 主要文件如下：

- [`app/src/main/java/org/openinputbridge/android/MainActivity.java`](app/src/main/java/org/openinputbridge/android/MainActivity.java)：Android App 主程序，管理设置页、WebView 生命周期、前台约束与 URL 校验。
- [`app/src/main/AndroidManifest.xml`](app/src/main/AndroidManifest.xml)：应用权限与网络配置。
- [`app/build.gradle`](app/build.gradle)、[`build.gradle`](build.gradle)、[`settings.gradle`](settings.gradle)：源码编译配置。
- [`../windows/ly03_voice_bridge_ws_v1.py`](../windows/ly03_voice_bridge_ws_v1.py)：Windows 接收端，以及在其 `PAGE` 字符串中直接提供给 WebView 的 **HTML/JavaScript 页面源码**。

App 并非将另一份不透明的网页或第三方插件打包进 APK；它连接本机局域网的 Windows 服务，网页由上述 Python 源文件提供。因此审查完整链路需要同时检查 Android Java 源码和 Python 中嵌入的网页代码。

**可自行从源码构建并安装**，也可以对比 Actions 工作流 [`.github/workflows/android.yml`](../.github/workflows/android.yml) 和 [`.github/workflows/publish-android.yml`](../.github/workflows/publish-android.yml) 的构建指令。仓库**源代码树**不提交 APK 二进制；预编译 APK 作为 GitHub Release 附件发布，同时附上相同 tag 的源码压缩包和 SHA256 校验文件。发布的 APK 是调试工件，不等于经过独立安全审计、可重现构建验证或真机验收。

## 适用范围与状态

- **Android 14 / API 34 或更新版本**（当前 `minSdk 34`）；需要可连接 Windows 的可信私人 Wi-Fi。
- 启动后在设置页粘贴 Windows 控制台当前打印的 **完整局域网 URL（含 `?token=...`）**，点击“连接并进入桥接”。
- **必须保持手机解锁、不锁屏，且 Open Input Bridge 界面始终在前台、可见并拥有焦点。** 桥接界面请求屏幕常亮；切到其他 App 后 WebView 页面会暂停/清空，恢复前台才重新加载连接。后台不转发。
- 2026-11-03 用户反馈：已从本项目 Release 下载并安装 Android App，确认可用。**这只是实际安装使用反馈**，不等于全部手势、焦点切换与休眠唤醒已通过系统验收。可使用 [Android Chrome 方案](../README.md) 作为对照。

## 编译 / 获取测试 APK

**推荐从 [GitHub Releases](https://github.com/VincentPeng207/open-input-bridge/releases) 直接下载版本化 APK**：选择 Android 预发布版本（如 `android-v0.1.0-preview.1`），在 Assets 附件中下载 `Open-Input-Bridge-Android-...-debug.apk`，同时可下载 `SHA256SUMS.txt` 进行校验。Release 自带 `Source code (zip)` 和 `Source code (tar.gz)`，可查看与 APK 对应的源码。

作为替代方案，GitHub Actions 中 `Build Android foreground app` 仍会上传 `open-input-bridge-android-debug` ZIP 工件，但 Actions 工件可能过期；**Release 才是建议用户下载 APK 的稳定入口**。APK 安装可能需要在 Android 系统中允许从文件管理器安装应用。

如自己编译：安装 JDK 17、Android SDK Platform 35、Gradle 8.10.2，然后在 `android/` 目录执行：

```bash
gradle :app:assembleDebug --no-daemon
```

输出应在 `android/app/build/outputs/apk/debug/app-debug.apk`。不包含 Gradle Wrapper 的二进制文件；请自行准备符合版本的 Gradle 或使用 CI。debug APK 使用调试签名，**不是正式安全审计或商店发布版本**。

## 使用步骤

1. Windows PowerShell：`py -3 .\windows\ly03_voice_bridge_ws_v1.py --dry-run --hotkey "ctrl+win"`（在仓库根目录运行）。**默认占用 TCP 8766 端口**；若端口已被其他程序使用，需添加 `--port 8767` 等参数自行指定空闲端口。
2. Android 蓝牙设置正常配对 LY-03，启动 Open Input Bridge，在“设置”中填入本次完整 URL，连接后保持页面前台和屏幕亮起。
3. 在 Android 界面使用手动测试按钮，再用 LY-03 中键和上下操作测试 Windows 终端日志。无键盘输入的 `DRY-RUN` 不会操控 Windows 应用。
4. Windows 停止服务并去掉 `--dry-run` 重启，复制**新的** token URL 给 App。先在语音输入软件中设置 `Ctrl+Win` 为启停热键，或为 `--hotkey` 指定别的已配置热键。中键快速双击发送 `Enter`。
5. 指环休眠后，如无反应，可按住中键**约 2 秒尝试唤醒/恢复蓝牙连接**，待 Android 蓝牙显示已连接后再次单击；此操作效果应在实际 LY-03 型号上复验。

## 已知限制

- Android App **已提供源码和 Release APK，且用户确认安装后可正常使用**；但全套真机验收（快速双击、失焦、休眠唤醒、长期稳定性）尚未完成。
- 地址只允许可信私人 IPv4 地址的 `http://` URL；不支持外网地址或 HTTPS。
- Windows 接收程序每次重启都更换 token，App 中此前保存的链接将失效，需要重新在设置页填入。
- App 不能代替 Windows 语音输入法本身；热键是否启动语音取决于你的软件配置和窗口焦点。
- 退出前台、手机锁屏、网络断开或指环休眠会中断控制；断线指令不补发。
