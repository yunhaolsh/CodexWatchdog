# CodexWatchdog

将 PC 上的 Codex 任务状态同步到 StackChan。当前已实现 PC Daemon、CLI 任务提交、
HTTP 查询和 WebSocket 状态推送。固件、设备审批和语音尚未完成。

开发状态见 [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)。

## 安装与测试

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

测试会创建临时的本机 HTTP/WebSocket 服务，启动 `tests/fixtures/mock_codex.py`，
不会调用模型或真实 Codex。需要允许本机 socket 和子进程。

## 启动常驻 Daemon

在仓库根目录执行：

```bash
python -m daemon.app serve
```

该进程同时启动：

- HTTP 控制 API：`http://127.0.0.1:12880`
- 设备 WebSocket：`ws://127.0.0.1:12800/stackChan/ws`

首次启动自动生成 `.run/token`（权限 0600，不提交 Git）。所有终端默认从当前目录读取
同一 token 文件；在其他目录启动命令时使用 `--token-file /绝对路径/.run/token`。
端口占用时指定 `--port` 和 `--api-port`，客户端也要指定相同的 `--api-port`。

## 设备模拟器

第二个终端，在同一目录执行：

```bash
python -m daemon.app simulate-device
```

终端会显示 hello 和最新状态。它连接的是真实 WebSocket 服务，支持断线重连。
单次只允许一个配对设备在线。当前身份为 `stackchan-1`，可在服务端和模拟器
同时用 `--device-id` 改变。

## 提交与查询任务

第三个终端执行（需要 Codex 已登录，将调用真实模型）：

```bash
python -m daemon.app run "只阅读 README，给出三句话摘要，不修改文件" --cwd "$PWD" --wait
python -m daemon.app status
```

`run` 向常驻 Daemon 提交任务，不会创建另一个孤立运行时。省略 `--wait` 即提交后返回
任务 ID。模拟器应显示 `running`、命令或回复摘要、最终 `success`/`failed`。
`success` 表示本轮完成且进程退出码为 0，不表示任务结果经过独立正确性验证。

要启用真实结构化审批，先使用：

```bash
python -m daemon.app serve --backend app-server
```

该后端把设备的 Allow/Reject 转发为 app-server 的一次性 `accept`/`decline`，
尚未在设备上提供 `acceptForSession` 或网络策略编辑。

`--legacy-device` 仅针对旧 StackChan 头像/通话固件，未验证适用于当前实机。
它不适用于 ESP-Claw 或 AI.AGENT 协议，不应作为实机验收的默认方案。

遇到“任务完成但屏幕无显示”，先运行：

```bash
python -m daemon.app doctor
```

`device_transport: disconnected` 表示任务消息没有设备接收，退出码为 2。
连接成功也不等于屏幕显示成功。诊断会列出 USB 序列号，不打开串口或复位设备。
详细现场记录见 [设备诊断](docs/DEVICE_DIAGNOSIS.md)。

legacy 模式不验证 Watchdog token，只发送旧版 `TextMessage` 帧（`0x07`），
仅处理固定心跳回复，其他入站动作均被忽略，不能参与审批。
已实现旧协议应用层心跳：每轮发送 `0x10`，等待 `0x11`，超时关闭连接；
自动化已验证回复、超时和重连，实机显示仍需验收。

### 已恢复固件的屏幕测试

对于按照 [恢复记录](docs/FIRMWARE_RECOVERY.md) 刷入的 StackChan 固件，
首次先在设备 `SETUP` 中配网，再从桌面进入 **AVATAR** 测试显示。
AI.AGENT 使用不同协议，当前测试服务不支持这个入口。

PC 接收端：

```bash
python -m daemon.app serve --host 0.0.0.0 --legacy-device
```

固件默认访问 `stackchan-nanobot.local:12800`；需要发布这个主机名为当前 PC
的局域网地址。本地已有 Demo 可复用以下脚本（单独运行，地址按实际填写）：

```bash
python /home/yunhao/github/stackchan/scripts/mdns_alias.py \
  --name stackchan-nanobot.local --address 192.168.18.6
```

设备进入 AVATAR 后，服务应记录 `Device connected`，屏幕应收到
`Ready / 就绪`。先验证这条固定文字，再运行 Codex 任务。
切换局域网后需更新发布地址；上述手动服务不是系统自启动服务。

```bash
python -m daemon.app cancel TASK_ID
```

每次只运行一个任务，重复提交返回 409。取消或停止服务时会终止所启动的 Codex
进程组。内存保留最近 100 个任务状态，服务重启后清空。

## 协议与当前边界

服务端使用 `Authorization: Bearer <token>` 鉴权，设备连接后首先发送：

```json
{"type":"hello","version":1,"device_id":"stackchan-1"}
```

服务端返回 hello 和当前 `task.status`。每次重连重放最新状态，使用 WebSocket
ping/pong 检测断线，拒绝错误路径、错误 token 和重复连接。

仅保留原 StackChan 的路径名称不代表兼容原固件：旧 `/stackChan/ws` 是头像/通话协议，
另有 Xiaozhi `/ws` 音频协议。目前两者都不会自动识别这里的 `task.status`。
需要后续适配固件，当前不要据此刷机或更改原 Demo 的服务器配置。

将来设备通过局域网连接时使用 `serve --host 0.0.0.0`。HTTP 控制端口仍仅监听 loopback。
当前是局域网明文 WebSocket，尚未实现 TLS 或自动发现。

当前默认后端为 `codex exec --json`，只做监控；`AppServerTaskAdapter` 已实现真实
`app-server --stdio` 的 thread/turn 和审批 future，但尚未成为默认后端。设备动作在
`exec` 模式会返回 `approval_unavailable`，只有 app-server 模式才会转发批准/拒绝。
语音、提示音乐和固件灯效同样尚未实现。

参考：[Codex 非交互模式](https://developers.openai.com/codex/noninteractive)、
[Codex app-server 审批接口](https://developers.openai.com/codex/app-server)。

## HTTP API

所有 API 要求相同的 Bearer token，`POST` body 是 JSON 对象，最大 64 KiB。

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/health` | 服务、设备连接、任务占用、审批支持状态 |
| GET | `/status` | 当前任务快照 |
| POST | `/tasks` | 提交 `{"prompt":"...","cwd":"/absolute/path"}` |
| GET | `/tasks/{id}` | 查询指定任务快照 |
| POST | `/tasks/{id}/cancel` | 取消任务，body 为 `{}` |

旧的 `python -m daemon.server` 独立 HTTP 测试服务已经停用，请使用统一的 `serve`。
