# StackChan 恢复与后续开发基线

## 目标及范围

目标 USB 序列号为 `44:1B:F6:E5:62:28`。必须使用 by-id 路径；
ACM0/ACM1 编号会互换。不得向另一台 `AC:27:6E:D2:FD:C8` 写入。

本次先恢复原 StackChan 屏幕和配网基础，便于后续加入 Watchdog 状态页、
触摸审批、LED 和音频。恢复原固件不等于实现 Watchdog v1 协议。
当前 AI.AGENT 使用 Xiaozhi，AVATAR 使用旧头像协议。

## 源码与构建

- 源码：`/home/yunhao/github/stackchan/StackChan/firmware`
- StackChan 提交：`69a8415482e4ecad97cd916fb0fd97e953ed6650`
- ESP-IDF：`/home/yunhao/github/stackchan/esp-idf`
- Python 环境：`/home/yunhao/.espressif/python_env/idf5.5_py3.13_env`
- 关键配置：ESP32-S3、M5STACK_STACK_CHAN、Quad PSRAM、16MB Flash。
- 完整 sdkconfig 和实际镜像保存在本机 `.run/recovery/firmware/`，不提交。

```bash
export IDF_PYTHON_ENV_PATH=/home/yunhao/.espressif/python_env/idf5.5_py3.13_env
export PATH="$IDF_PYTHON_ENV_PATH/bin:$PATH"
source /home/yunhao/github/stackchan/esp-idf/export.sh
cd /home/yunhao/github/stackchan/StackChan/firmware
idf.py build
```

复制构建产物时必须包含 flash_args 引用的全部镜像，包含字体等 assets。
`.run/recovery/firmware/manifest.json` 记录本次产物的 SHA256。

## 备份与刷写

先读取芯片身份和物理 Flash 容量，再备份完整 Flash；本次读取得到 16MB。
备份含设备配置，位于权限受限且被 Git 忽略的 `.run/recovery/`。
备份文件不属于可用恢复固件：它保存的是本次修复前无法启动的状态。

以下命令要求先完成并检查备份，且设备仍是上述 USB 序列号：

```bash
cd /home/yunhao/Demos/AgentWatchDog/CodexWatchdog/.run/recovery/firmware
/home/yunhao/.espressif/python_env/idf5.5_py3.13_env/bin/python -m esptool \
  --chip esp32s3 \
  --port /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_44:1B:F6:E5:62:28-if00 \
  --baud 460800 --before default_reset --after hard_reset \
  write_flash @flash_args
```

按镜像地址写入并校验，不全片擦除。新分区表的 NVS 为 0x9000/0x4000，
此区域不在镜像写入范围；原先另一套固件的 NVS 为 0x9000/0x6000，
布局变化仍可能影响旧配置可读性，不能保证所有旧配置被保留。

## 验收边界

刷写工具校验成功后，还需从串口确认 PSRAM 正常、应用进入 Launcher、
不再持续重启；屏幕点亮、触摸及配网由实机观测确认。
先恢复启动再配网，不在黑屏或循环重启时指导进入 SETUP。
联网后才能继续 Watchdog 协议适配和任务状态验收。


## 2026-09-09 本次刷写结果

- 完整备份：`.run/recovery/stackchan-before-recovery-20260909.bin`，16,777,216 字节。
- 备份 SHA256：`62b86402b18c5ee285745ee09805001007dcbb100e6f3aa0364f69a407b6f2ca`。
- 新应用 SHA256：`574139f975f1213215c4ad9926c51d78797610b4ffec6bd90a91efb055a37038`。
- `idf.py build` 成功；5 个镜像写入成功，esptool 校验通过，退出码 0。
- 使用 esptool 官方 USB 硬复位后抓到以下启动日志：

```text
esp_psram: Found 8MB PSRAM device
esp_psram: Speed: 80MHz
app_init: Project name:     stack-chan
app_init: App version:      1.4.3
esp_psram: Adding pool of 8192K of PSRAM memory to heap allocator
main_task: Calling app_main()
[HAL] creating hal instance
[HAL] init
[HAL] xiaozhi board init
```

PSRAM 初始化已通过，不能据此声称桌面、Wi-Fi 或 Watchdog 实机验收完成。
本地时间 23:12:26 内核记录目标 USB 断开，随后只剩另一块板的 USB 序列号。
日志在 Board 初始化阶段中断，尚未捕获 Launcher；待用户保持目标供电并重新连接，
继续检查启动与屏幕。断开原因未确认，不将其归因于用户操作或固件故障。

构建、刷写、启动原始日志分别在 `.run/recovery/build.log`、`flash.log`、
`boot-reset.log`。本次未修改旧 StackChan 仓库的已跟踪源码。
