# Verification / 公开验收说明

[中文 README](../README.md) · [English README](../README.en.md) · [Android 说明](../android/README.md)

本文记录可复现的验收步骤、自动化测试范围、已报告的真实使用情况以及尚未系统验证的功能。

## 已实现的范围 / Implemented

- Windows Python 接收端：2026-11-03 用户观察到 `tap -> ctrl+win (SENT)`，确认接收端实际发送了配置的快捷键。此前 Android Chrome 链路有真实设备成功记录；本次未单独完成 Chrome 的全部验收矩阵。
- Android 前台 WebView App：源码和 Release 调试 APK 已提供；2026-11-03 用户反馈**已从 Release 下载并安装、确认可用**。未提供逐项测试记录，因此**双击可靠性、失焦与休眠恢复仍待系统测试**。
- 中键单击：默认 `Ctrl+Win`，用于应用自己配置的语音启停热键；快速双击：`Enter`。上下操作：默认各执行 8 次方向键；上下快速双击**不作为受支持的物理功能**。
- 手机必须**不锁屏、亮屏且桥接 App/浏览器在前台活动状态**；LY-03 休眠时可**长按中键约 2 秒尝试唤醒/重连**，具体成功率待真机确认。断线输入不补发。

## 真机验收 / Device acceptance

每次验收记录：源代码 commit SHA、Windows/Python/Android/Chrome 版本、LY-03 设备变体、手机品牌型号、Wi-Fi 环境、测试入口（App 或 Chrome）。**不要记录完整 token URL。**

- [ ] Windows 接收端用 `--dry-run` 启动；选正确的私人 IPv4 地址，连接后能看到“在线”和心跳 RTT；界面内手动 `tap` / `double` / `up` / `down` 对应日志正确
- [ ] Android Chrome：屏幕亮、解锁、页面前台，物理中键单击**只发一个 tap**；快速双击**只发 double，不先发 tap**；至少做 10 次记录误判次数
- [x] Android App：用户于 2026-11-03 从 Release 下载 APK 并确认安装后可使用（用户报告，未留逐项测试日志）
- [ ] Android App：逐项验证 WebView 物理按键、双击成功率、离开前台/锁屏停止发送、恢复重连（尚未完成完整验收）
- [ ] 中键分别点击两次（间隔数秒），配置的语音输入法可以开始/停止；将语音输入法热键与 `--hotkey` 同时改为另一组合时可正常使用
- [ ] 短促上下操作产生 `up` / `down`，每次默认 8 步；真实滑动方向符合用户期望；不要求支持上下双击
- [ ] 停止 `--dry-run` 后重启 Windows 服务，App/Chrome 更新 token，在 Windows 记事本上使用 `--hotkey "ctrl+a"` 验证键盘注入，再验证语音快捷键
- [ ] 断开再恢复 Wi-Fi，断线期间操作**不应补发**；旧 token 被拒绝、新 token 可连接
- [ ] LY-03 闲置进入休眠后，记录首次无响应现象；长按中键**约 2 秒**尝试恢复蓝牙连接并重新单击，记录实际响应和时延
- [ ] 手机锁屏、App/Chrome 切后台后不能继续控制；恢复顶层活动时的重连情况已记录
- [ ] 不同网络、长时间运行（建议至少 2 小时）的断连与输入遗漏情况已记录

## 自动化检查 / Automation

- `python -m compileall -q windows`：Python 静态语法检查
- `python -B -m unittest discover -s windows -p "test_*.py" -v`：Windows 键位映射、WebSocket、无 token 403、重复动作去重、非法命令拒绝、连接重置处理
- `node windows/test_directional_classifier.js`：18 个嵌入网页事件模拟场景
- `android/`：GitHub Actions 编译 Java + Android Gradle 工程并上传调试 APK
- 以上均不能代替真机 LY-03 + Android + Windows 的输入验收

**公开前核对 / Public readiness：** Windows/Ubuntu 回归 CI 和 Android APK 构建已通过，且有上述用户实测反馈；公开历史必须不再包含内部迁移文件与测试环境信息，且需核对源码及第三方依赖许可。完整真机矩阵未完成的项目应保持如实标注，不宣称全面兼容。当前仓库可见性由维护者另行决定。
