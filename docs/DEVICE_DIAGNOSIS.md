# 屏幕未显示诊断（2026-09-09）

## 已观测

- 用户的真实 Codex 任务完成，模拟设备曾完整收到任务状态。
- 屏幕失败时 Daemon `/health` 返回 `device_connected: false`。
- PC `0.0.0.0:12800` 和 `127.0.0.1:12880` 正常监听。
- PC mDNS 解析 `stackchan-nanobot.local` 为 `10.109.161.191`。
  这只证明 PC 本地解析，不能证明 ESP 能访问该地址。
- 同时插入两块 Espressif USB Serial/JTAG 设备。

| 当前端口 | USB 序列号 | 证据 |
| --- | --- | --- |
| `/dev/ttyACM0` | `44:1B:F6:E5:62:28` | 与旧 StackChan E562xx 记录对应的候选设备；被动读取无输出，当前固件待确认 |
| `/dev/ttyACM1` | `AC:27:6E:D2:FD:C8` | 启动日志为 `esp-agent-demo`，版本 `0a52f7f-dirty`，SH8601 466x466、8MB flash，不是目标 StackChan |

ACM1 串口操作中观测到 `USB_UART_CHIP_RESET`，后续停止操作该设备。未刷写任何设备。
后续用 `/dev/serial/by-id/` 选择设备，不凭 ACM 编号或串口是否输出判断身份。

## 原因与纠正

直接原因是目标设备未接入 Daemon。之前从 `StackChan/firmware` 源码推断当前设备
支持旧头像 `0x07 TextMessage` 的依据不足，且把 ACM1 错认成 StackChan。
旧目录的配置不能证明当前实机固件或网络配置。

历史文档另指出 ESP-Claw 源码位于 `/home/yunhao/github/esp-claw/application/edge_agent`。
这同样不能证明当前 ACM0 正在运行 ESP-Claw。需要用户界面信息或该设备自身版本输出。

## 后续顺序

1. 用 `python -m daemon.app doctor` 检查设备连接，避免反复调用 Codex 测试屏幕。
2. 确认目标 StackChan 的 Ready 界面含义及实际固件，不操作 ACM1。
3. 根据固件确认现有控制接口或实现 Watchdog 固件组件。
4. 首先推送固定测试文字验证显示，再进行任务流验收。

诊断命令只枚举 USB 元数据，不打开串口；连接日志不打印 token 或任务内容。

## 原 StackChan 应用入口

以下结论来自本地 `StackChan/firmware/main/apps` 源码，只描述该源码版本，
实际刷入设备的版本仍需启动日志确认。

| 界面 | 源码行为 | 与 Watchdog 的关系 |
| --- | --- | --- |
| 桌面/启动界面 | 不能从屏幕已点亮推断网络连接 | 不代表已经连接 Watchdog |
| `AVATAR` | `app_avatar.cpp` 的 `onOpen()` 调用 `startWebSocketAvatarService()`，注册 `onWsTextMessage` | 对应旧 `/stackChan/ws` 二进制文本帧；仅此路径可能适用 legacy 模式 |
| `AI.AGENT` | `app_ai_agent.cpp` 的 `onOpen()` 调用 `requestXiaozhiStart()` | 使用 Xiaozhi 路径，不能用 legacy 头像协议推送文字 |

不要仅凭用户提到“StackChan 界面”或“Ready”选择协议。优先在用户短按 RST 后，
使用已有 `scripts/diagnose_stackchan_serial.py` 对指定 USB by-id 做只读监听。
该脚本使用 `os.open`，不调整 DTR/RTS；没有日志时记录“未知”，不猜测当前固件。
