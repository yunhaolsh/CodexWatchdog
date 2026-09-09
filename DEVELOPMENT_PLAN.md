# CodexWatchdog 开发路线

## 已确定的需求

- PC 上以 Codex CLI 开始，后续支持 Desktop。
- 一台 StackChan，屏幕中英混合；运行红灯闪烁，等待权限黄灯慢闪，完成绿灯常亮。
- 设备能批准/拒绝真实权限请求，完成时播放提示音乐。
- 后续语音下发和查询任务。
- 每个可独立验证的阶段完成后测试并提交；最后统一安排实机验收。

## 开发约定

只复用 `/home/yunhao/github/stackchan` 中已确认的硬件组件和工具链，不默认覆盖旧 Demo。
每个阶段区分代码完成、自动化验证、实机验证。测试通过不等于固件或真实 Codex 已验收。
不要从 `codex exec` 的进程输出猜测权限请求，不能把本地显示变化视为批准成功。

## Phase 0：基线

- [x] 确认本地已有 ESP-IDF 和 StackChan 工程。
- [x] 确认 Codex CLI 支持 `exec --json`。
- [x] 建立 Python 包、依赖、测试和 Git 仓库。
- [ ] 确认实际 USB 串口、板型、当前固件和 ready 模式含义。
- [ ] 记录现有固件及恢复方法，检查可用构建环境。

## Phase 1：PC 完整链路

- [x] 同一 Daemon 持有 HTTP 控制、任务运行器和设备 WebSocket。
- [x] `run` 提交至常驻 Daemon，支持状态查询、单任务限流和取消。
- [x] Codex JSONL 解析命令/回复/完成/失败；关闭服务清理子进程。
- [x] Bearer token、配对 device_id、握手超时、心跳和重复连接限制。
- [x] 重连保留并重放最新状态。
- [x] 模拟设备连接真实服务，独立 CLI 进程提交本地模拟任务。
- [x] 自动化验证 HTTP/WS 鉴权、连接恢复、非零退出、缺失完成和取消。
- [ ] 用户通过真实 Codex 任务验证显示状态。

自动化使用 mock Codex 进程，不调用模型。当前完成的工作以此阶段为界。

## Phase 2：真实审批后端

- [ ] 读取当前 `codex app-server` 生成的 schema，确认 initialize、thread、turn 接口。
- [x] 读取当前 CLI 生成的 v2 schema，完成 `app-server --stdio` initialize 握手客户端。
- [x] 暴露 app-server server-notification 回调和严格审批响应对象。
- [x] 实现 app-server 的 thread/turn 启动、审批挂起和设备 action 恢复骨架。
- [ ] 将 app-server 后端接入 Daemon 的 `run --backend app-server`。
- [ ] 接入 `item/commandExecution/requestApproval` 和文件变更审批。
- [ ] 关联 task/thread/turn/request ID；单次批准或拒绝，防重放和过期操作。
- [ ] 审批的可用选项以服务端请求为准。
- [ ] 断线、已在 PC 回答、任务取消和超时应使设备按钮失效。
- [ ] 集成测试必须核验响应实际写回 Codex，而不是只更改屏幕。

`exec --json` 当前只做监控，设备动作明确返回 `approval_unavailable`。
官方 app-server 提供结构化审批通道，应先验证它，再决定是否需要任何 PTY 方案。

## Phase 3：固件

- [ ] 在新仓库内建立可复现的固件构建或组件接入方式。
- [ ] 设备主动连接 PC，使用 Watchdog v1 hello 和状态协议。
- [ ] 增加显示页：当前阶段、摘要、连接状态、权限内容和 Allow/Reject。
- [ ] 状态灯：idle 熄灭、running 红闪、waiting 黄闪、success 绿常亮、failed 红常亮。
- [ ] 心跳超时进入 offline，不保留误导性的成功状态。
- [ ] 完成/失败提示音；重复快照不重复播放音乐。
- [ ] 编译、刷写、屏幕/灯光/触摸/音乐实机验收。

旧工程中的 `/stackChan/ws` 是头像/通话协议，Xiaozhi `/ws` 是另一套协议。
路径可沿用，但 `task.status` 与鉴权必须显式适配，不能认为当前固件已经兼容。

## Phase 4：语音

- [ ] 复用设备录音、上传与音频播放能力。
- [ ] 选择 ASR 接入，先实现“当前任务”“最近结果”“停止任务”。
- [ ] 语音下发任务先显示转写和工作目录，确认后提交。
- [ ] 语音响应或提示音，处理噪声、空转写和断网。

## Phase 5：运行与发布

- [ ] 任务历史持久化和 Daemon 重启恢复规则。
- [ ] 配置文件、systemd/启动脚本、局域网地址发现。
- [ ] 文档：安装、配对、刷机、回退和故障诊断。
- [ ] 真实 CLI 和 StackChan 完整闭环验收；之后考虑 Desktop。
