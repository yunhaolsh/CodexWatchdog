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
| `/dev/ttyACM0` | `44:1B:F6:E5:62:28` | 后续只读监听确认 `stack-chan` 1.4.3，ESP32-S3、16MB flash、8MB PSRAM；编译于 2026-08-31 |
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
2. 目标身份已确认；先恢复 Wi-Fi，再确认服务地址和协议，不操作 ACM1。
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

## AI.AGENT 扫描 Wi-Fi 时的实机故障

用户进入 AI.AGENT 后，使用上述 by-id 只读监听，捕获到以下顺序：

```text
WifiStation: No AP found, next scan in 30 seconds
SystemInfo: free sram: 6851 minimal sram: 47
WifiBoard: WiFi connection timeout, entering config mode
WifiManager: Starting config AP
wifi:alloc eb len=752 type=4 fail
Guru Meditation Error: Core  0 panic'ed (LoadProhibited)
EXCVADDR: 0x0000002c
Backtrace: 0x421e5dee:0x3fcf3e00 0x421e69f2:0x3fcf3e60 0x421f27e1:0x3fcf3ea0 0x421f4467:0x3fcf3ec0 0x421f25ea:0x3fcf3ee0 0x42267eb1:0x3fcf3f00 0x4038fbed:0x3fcf3f30
ELF file SHA256: 4b919ca8f
Rebooting...
app_init: Project name:     stack-chan
app_init: App version:      1.4.3
app_init: Compile time:     Aug 31 2026 13:40:43
```

结论：扫描失败后切换配网热点发生分配失败及崩溃；这不是等待 Codex 任务。
低 SRAM 与分配失败同时出现，但尚未定位内存耗尽来源，不能宣称根因已修复。
本地 `firmware/build/stack-chan.elf` SHA256 为
`bea159568d6013b815f1cf6875f9f352c0810240a9742f33205fc85d87b0dde7`，
与实机不同，不用它把崩溃地址映射成确定的源码行。

PC 当前关联 `lenovo-5G`，频率 5765 MHz。ESP32-S3 仅支持 2.4 GHz Wi-Fi，
见 [Espressif 产品说明](https://www.espressif.com/en/products/socs/esp32-s3)。
此记录不代表知道设备保存的 SSID，也不能断定频段是扫描失败的唯一原因。
PC 可继续使用同一路由器的 5 GHz 网络，前提是两个频段的客户端可互通。

建议先在设备重启后的桌面进入 `SETUP`，按屏幕指引通过 StackChan World
配置可达的 2.4 GHz 网络。本地 `app_setup/workers/connectivity.cpp` 对应流程为
`APP SETUP` -> `Next` -> 手机连接 -> `Ready to Configure ~` ->
`Verifying...` -> `Done! Reboot in ...`，Ready 本身不代表配网成功。
尚未实机验证该入口能避开 Agent 模式下的低内存故障。

联网后仍需处理 AI.AGENT 的 Xiaozhi OTA/WebSocket 接口；当前 Watchdog
`--legacy-device` 不是该接口的实现。先验证联网、服务握手和固定文字显示，
再让用户重跑 Codex 任务。


## 22:58 持续黑屏：启动阶段 PSRAM 初始化失败

再次按 USB 序列号 `44:1B:F6:E5:62:28` 只读监听，确认目标现在映射到
`/dev/ttyACM1`（另一块板是 ACM0），内核记录目标频繁断开并重新枚举。
本次串口反复输出：

```text
boot: ESP-IDF v5.5.4-dirty 2nd stage bootloader
boot: compile time Aug 27 2026 22:39:21
boot.esp32s3: SPI Flash Size : 8MB
boot: Loaded app from partition at offset 0x10000
E (517) octal_psram: PSRAM chip is not connected, or wrong PSRAM line mode
E cpu_start: Failed to init external RAM!
abort() was called at PC 0x420039f3 on core 0
Rebooting...
```

此时分区名为 nvs/phy_init/factory/cmm/assistant/model，与此前目标的
nvs/otadata/phy_init/ota_0/ota_1/assets/coredump 不同；启动固件发生变化，
不能继续按此前已进入 AI.AGENT 的状态判断。无法仅凭日志判断由谁、何时刷入。
8MB 是本次启动配置输出，不代表设备物理 Flash 容量变成了 8MB。

本地 StackChan 固件 sdkconfig 使用 `CONFIG_SPIRAM_MODE_QUAD=y` 和 16MB Flash，
本次启动却进入 octal_psram 初始化并失败，固件与硬件配置不匹配是优先排查方向，
尚不能据此排除硬件故障。本地 esp-claw edge_agent sdkconfig 是 Octal/8MB，
仅配置相似，不足以断定当前刷入固件的项目身份。

应先确认最近是否刷入其他固件及其来源，再准备匹配此板的恢复镜像；
恢复启动后才能配网。本次操作仅枚举 USB、读取内核日志和只读串口，未刷写。
现有外部 diagnose_stackchan_serial.py 在出现 SPI_FAST_FLASH_BOOT 时会误报
“Firmware appears to be booting”，本次明确以原始 PSRAM 错误和反复重启为准。


## 用户授权后的固件恢复

用户明确要求直接刷机后，已对目标读取硬件身份、备份完整 16MB Flash、
重新编译并刷入 Quad PSRAM 配置的 StackChan 固件。镜像校验成功，启动日志
确认 PSRAM 初始化成功并进入 app_main。后续 USB 断开导致尚未确认 Launcher
和实际屏幕状态，详见 [恢复记录](FIRMWARE_RECOVERY.md)。
