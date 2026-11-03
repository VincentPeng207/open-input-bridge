# Contributing / 贡献指南

Open Input Bridge accepts device adapters, bug reports, documentation fixes and additional bridge/receiver implementations. Start by describing the **exact device model, OS, event sequence, reproducible steps and actual test status**. Do not imply that a new operating system or hardware is supported until it has been tested on real hardware.

**Keep the working contract stable:** browser `type: "action"` with `id` and `cmd` values `tap`, `double`, `up`, `down`; `up_double` / `down_double` are legacy-compatibility receiver commands, not current browser gestures. The sender never replays actions after disconnection. Any behavioral/protocol change needs clear motivation, tests, and an updated verification matrix.

Before a PR, run the Python/Node commands from the README and explain which were skipped. Prefer one minimal device-specific adapter over a general plugin framework in the first phase. Do not submit APKs/binary artifacts, generated caches, tokens, captured URL screenshots, private device identifiers, internal product documents or third-party source code without provenance and license review.

**中文：** 优先提交可复现的最小修复；清楚标注“静态检查 / 模拟测试 / 真机测试”的差别。新增设备先说明事件输入、映射及限制，不要为了扩展性重构现有通道。不要提交 token、私有研发文档、供应商资料或未经授权的第三方文件。
