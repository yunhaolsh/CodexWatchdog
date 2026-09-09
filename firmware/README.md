# WATCHDOG 固件

这是基于已恢复 StackChan 固件的显示组件。桌面原 AVATAR 入口改名为
**WATCHDOG**，打开后显示常驻任务页，不再回到仅有表情的画面。

- 标题显示任务阶段；正文可上下滚动。最终回复保留到下一任务或退出应用。
- 运行红灯闪烁，等待确认黄灯慢闪，成功绿灯常亮，失败红灯常亮。
- 取消或连续 12 秒未收到状态/心跳时熄灯；离线时保留最后文字并明确标识 OFFLINE。
- 在本次连接期间观察到运行状态后，首次完成/失败播放短三音提示。
  重连收到同一完成快照不重复播放；首次打开收到历史完成结果不播放。
- 底部 Home 手势可退出。当前不提供批准/拒绝按钮，审批仍待鉴权协议阶段。

这次沿用旧头像二进制 TextMessage (0x07) 帧，并增加 `watchdog` 对象携带
完整 `task.status`。原 AVATAR 忽略扩展仍能读 `content`；新版读取扩展来
驱动标题、正文和灯效。服务仍需 `--legacy-device`，该通道未做设备身份鉴权，
只能用于局域网状态显示，不能批准任务。尚未完成 Watchdog v1 原生设备协议。

## 构建

`prepare.py` 将旧 Demo 复制到本项目的 `.run/watchdog-firmware`，应用
`overlay` 中的 UI 代码及少量结构化状态/心跳信号补丁，不修改旧 Demo。
依赖复用本地已有 ESP-IDF、managed_components、字体和 Xiaozhi 源码。
这些大文件与本地配置不提交仓库。

已构建的源版本：

- StackChan `69a8415482e4ecad97cd916fb0fd97e953ed6650`
- Xiaozhi `e77dedb1309153bb63fed285772962c920c97dd4`
- ESP32-S3 / M5STACK_STACK_CHAN / 16MB Flash / Quad PSRAM

```bash
python firmware/prepare.py
export IDF_PYTHON_ENV_PATH=/home/yunhao/.espressif/python_env/idf5.5_py3.13_env
export PATH="$IDF_PYTHON_ENV_PATH/bin:$PATH"
source /home/yunhao/github/stackchan/esp-idf/export.sh
cd .run/watchdog-firmware
idf.py build
```

准备脚本拒绝覆盖已有目录。再次从源码准备时用 `--output` 指定一个新目录；
修改 overlay 后，可将对应文件复制到已有独立副本进行增量编译。
当前准备工具依赖上述本地 Demo 完整资源，并非联网自动安装工具。

## 刷写与回退

目标必须通过 USB 序列号识别：`44:1B:F6:E5:62:28`，不能用 ACM 编号判断。

本次是在已恢复的相同分区布局上更新应用：已读取 OTA 选择记录，确认运行
ota_0（0x20000），并比对分区表和 assets 完全一致，故仅刷写应用分区。
此命令不适用于未知原固件、不同分区表或运行 ota_1 的设备：

```bash
cd .run/watchdog-firmware/build
/home/yunhao/.espressif/python_env/idf5.5_py3.13_env/bin/python -m esptool \
  --chip esp32s3 \
  --port /dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_44:1B:F6:E5:62:28-if00 \
  --baud 460800 --before default_reset --after hard_reset \
  write_flash --flash_mode keep --flash_size keep --flash_freq keep \
  0x20000 stack-chan.bin
```

Wi-Fi/设备配置备份为 `.run/recovery/config-before-watchdog.bin`，不提交。
旧的可用恢复镜像保存在 `.run/recovery/firmware/`，回退说明见
[恢复记录](../docs/FIRMWARE_RECOVERY.md)。

## 验收

打开 WATCHDOG 后应看到 `Ready / 就绪` 常驻页面。通过 PC 提交真实任务，
观察正文、滚动、红灯、绿灯和提示音；完成后等待至少 30 秒，文字不应消失。
断开服务后约 12 秒应出现 OFFLINE、LED 熄灭，重连后恢复最新状态。
这不是常驻任务历史数据库；Daemon 重启会清空内存中的任务与最终回复。

自动化覆盖结构化状态、旧帧兼容、最后回复保留及下一任务隔离；
固件编译通过和刷写校验不等于屏幕、触摸、灯光、音频的实机视觉/听觉验收。
