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

当前固件可先做屏幕冒烟测试：

```bash
python -m daemon.app serve --host 0.0.0.0 --legacy-device
```

legacy 模式是显式的临时兼容模式：当前固件发送旧版 hello 和自有 token，服务端因此
不验证 Watchdog token，只发送旧版屏幕 `TextMessage` 帧（`0x07`）。它不提供灯效或审批。
请只在可信局域网短时间使用，完成屏幕测试后关闭。

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
