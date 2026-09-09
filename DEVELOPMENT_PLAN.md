# CodexWatchdog 开发路线

## 目标

让一台 StackChan 成为 Codex CLI 的远程状态终端和交互入口：显示任务阶段、进度和权限请求；运行中红灯闪烁，等待确认黄灯慢闪，成功绿灯常亮，失败红灯常亮；支持在 StackChan 上批准或拒绝 Codex CLI 权限请求，并为后续触摸/语音启动任务和查询任务保留接口。

## 总体架构

```text
Codex CLI <-> AgentWatchdog Daemon <-> StackChan
                         |
                         +-- 本地任务状态与权限代理
                         +-- 语音输入/查询入口（后续）
```

Daemon 是 PC 上的桥接层，负责启动或连接 Codex CLI、解析事件、保存任务状态、向设备推送状态，以及把设备上的批准/拒绝写回 CLI 的交互通道。

## 分阶段实施

### Phase 0：环境和硬件基线

- [ ] 确认 StackChan 的实际串口设备、板型和当前固件版本。
- [ ] 从 `/home/yunhao/github/stackchan` 复用 ESP-IDF 环境和板级组件。
- [ ] 确认屏幕、RGB 灯、扬声器、触摸输入均可独立控制。
- [ ] 建立本仓库的 Python 开发环境和基础测试命令。

验收：能在本机刷写/运行一个最小固件，并通过串口看到设备状态。

### Phase 1：PC Daemon 与设备状态协议

- [ ] 定义版本化 JSON 消息协议。
- [ ] 实现单设备 WebSocket 客户端、重连、心跳和鉴权。
- [x] 确认 StackChan 主动连接 `/stackChan/ws?deviceType=StackChan`，并抽象单设备会话层。
- [ ] 实现本地 HTTP API：`/health`、`/status`、`/events`。
- [ ] 实现设备状态机：`idle`、`running`、`waiting`、`success`、`failed`、`offline`。
- [ ] 先用测试脚本模拟 Codex 事件，验证灯光、屏幕、提示音。

验收：无需启动 Codex，发送模拟事件即可完整驱动 StackChan 状态变化。

### Phase 2：Codex CLI 适配器

- [ ] 设计 `CodexEventSource` 接口。
- [ ] 优先验证 Codex CLI 的结构化输出/事件能力。
- [ ] 若权限交互仍是终端输入，使用 PTY 启动 CLI 并解析权限提示。
- [ ] 将开始、阶段变化、命令、权限请求、完成、失败统一成内部事件。
- [ ] 记录任务 ID、工作目录、开始时间、结束时间和最后结果摘要。

验收：执行 `agentwatchdog run ...` 时，StackChan 能同步显示开始、执行中、权限等待、成功/失败。

### Phase 3：StackChan 触摸确认

- [ ] 增加 `Allow`、`Reject` 两个可操作区域。
- [ ] 设备上报 `approve`/`reject`，包含 `task_id` 和 `request_id`。
- [ ] Daemon 校验请求是否仍然有效，避免重复或过期确认。
- [ ] 将确认结果写回 Codex CLI 的 PTY/输入通道。
- [ ] 增加超时、断线和拒绝后的清晰状态。

验收：用户不接触 PC 键盘，也能在设备上完成一次真实权限批准和拒绝。

### Phase 4：语音任务入口与查询

- [ ] 复用 StackChan 现有音频/WebSocket 能力。
- [ ] 先支持固定意图：启动任务、当前状态、停止任务、最近结果。
- [ ] 再支持自然语言转任务描述。
- [ ] 语音任务必须显示确认摘要，避免误启动高风险命令。

验收：用户可通过 StackChan 语音查询当前任务，并启动一个明确的 Codex CLI 任务。

### Phase 5：稳定性与发布

- [ ] 增加单元测试、协议测试和 PTY 集成测试。
- [ ] 覆盖设备断线、Daemon 重启、CLI 崩溃、重复确认和任务超时。
- [ ] 增加本地日志脱敏，不记录 API key 和完整敏感命令输出。
- [ ] 增加 systemd/启动脚本和配置文件。
- [ ] 编写刷机、回滚、故障诊断文档。

## 首版协议草案

PC 推送：

```json
{
  "version": 1,
  "type": "task.status",
  "task_id": "task_123",
  "state": "waiting",
  "phase": "permission",
  "title": "需要确认 / Approval required",
  "message": "执行 npm install",
  "request_id": "perm_456",
  "requires_action": true
}
```

设备上行：

```json
{
  "version": 1,
  "type": "task.action",
  "task_id": "task_123",
  "request_id": "perm_456",
  "action": "approve"
}
```

协议必须支持 `request_id` 幂等校验、状态序号、心跳和设备重连后的当前状态重放。

## 首版工程结构

```text
codexwatchdog/
├── daemon/
│   ├── server.py
│   ├── protocol.py
│   ├── stackchan_client.py
│   ├── codex_cli_adapter.py
│   └── task_state.py
├── firmware/
│   └── stackchan-codex-monitor/
├── tests/
├── pyproject.toml
└── README.md
```

## 风险与第一条实现任务

Codex CLI 权限交互方式是首要技术风险，先做 PTY/结构化事件探测。语音下发任务必须有确认摘要和高风险命令拦截。第一版只允许一台设备配对，使用随机 token；固件优先复用 StackChan 现有 WebSocket 和硬件能力。

首先完成 Phase 0 和 Phase 1 的 PC 侧最小闭环：建立 Python 包与测试框架，实现协议模型与状态机，实现模拟设备客户端/服务器，定义真实固件需要新增的最小消息处理接口，然后连接当前 ready 状态的设备实测。
