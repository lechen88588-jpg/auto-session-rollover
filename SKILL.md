---
name: auto-session-rollover
description: OpenClaw 长会话上下文治理：动态阈值监控、自动压缩、legacy 模型自动 rollover。大窗口模型（>200k）跳过 rollover 仅压缩，小窗口模型（≤200k）在硬触发时自动收口+退休+生成续跑提示。由 cron 调度器每 10 分钟巡检，无需人工干预。
---

# Auto Session Rollover V4.2

## 架构概览

```
cron (每10min) → watchdog.py → healthy? → 跳过
                              → soft?    → 警告
                              → hard?    → rollover.py → 追加退休标记 → 老板开新会话
```

### 核心组件

| 文件 | 作用 |
|------|------|
| `scripts/ctx_common.py` | 公共模块：配置读取、阈值计算、token 读取 |
| `scripts/watchdog.py` | 巡检脚本：输出 JSON 状态 + 退出码 |
| `rollover.py` | 收口脚本：清理日志、写 HOT_MEMORY、生成续跑提示、追加退休标记 |
| Cron `ctx-watchdog` | 每 10 分钟调用 watchdog，isolated session |

## 动态阈值（按模型自适应）

| 模型 contextWindow | 软触发 | 硬触发 | 策略 |
|---|---|---|---|
| ≤ 200k (legacy) | 150k | 180k | rollover（收口+退休+等新会话） |
| > 200k (large) | 75% | 90% | 仅压缩（大窗口够用，不 rollover） |

当前：MiMo v2 Pro = 1M → 软 786k / 硬 943k / 仅压缩

## 退出码语义

| 退出码 | action | 含义 |
|--------|--------|------|
| 0 | healthy / already_rolled | 正常，无需操作 |
| 1 | rollover_warning / compress_soft | 软触发，输出警告 |
| 2 | rollover_required / compress_hard | 硬触发，需要执行 rollover.py |

## rollover.py 行为

### 大窗口模式（need_rollover=false）
- 仅清理 3 天前 daily logs
- 不覆写 HOT_MEMORY.md
- 不生成 NEXT_SESSION_PROMPT.md
- 不追加退休标记

### Legacy 模式（need_rollover=true）
1. 清理 3 天前 daily logs（幂等，删不到不报错）
2. 从 HOT_MEMORY.md 提取：项目名、已完成、未完成、下一步
3. 生成 NEXT_SESSION_PROMPT.md
4. **追加** ROLLOVER 退休标记到 HOT_MEMORY.md（不覆写！）

退休标记格式：
```markdown
## ROLLOVER
- ROLLED_OVER: true
- ROLLOVER_TIME: 2026-03-27 10:30
- ROLLOVER_REASON: hard_trigger (185k/200k)
- ROLLOVER_MODEL: xiaomi/mimo-v2-pro
- ROLLOVER_MODE: V4.2-external-scheduler
```

## 与 HEARTBEAT.md 的配合

HEARTBEAT.md 每次心跳检查：
1. session_status 获取 token 用量
2. 检查 HOT_MEMORY.md 是否有 `ROLLED_OVER: true`
3. 若已退休 → 提示老板开新会话，不回复 HEARTBEAT_OK

## 手动运行

```bash
# 查看当前状态
python3 ~/.openclaw/workspace/scripts/context-watchdog.py

# 手动执行 rollover（脚本自行判断是否需要）
python3 ~/.openclaw/workspace/skills/auto-session-rollover/scripts/rollover.py
```

## Cron Job 管理

```bash
# 查看状态
openclaw cron list

# 手动触发测试
openclaw cron run <job-id>

# 暂停
openclaw cron edit <job-id> --disabled
```

## 不能用的路

| 方案 | 原因 |
|------|------|
| sessions_spawn(streamTo:parent) | subagent 不支持此参数 |
| sessions.delete(agent:main:main) | Gateway 拒绝删除主会话 |
| 外部 shell crontab | 需处理 PATH/环境变量，不如内置 cron |
