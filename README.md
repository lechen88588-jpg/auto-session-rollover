# Auto Session Rollover V4.2

OpenClaw 长会话上下文自动治理技能。

## 功能

- **动态阈值**：自动读取模型 contextWindow，按比例计算触发阈值
- **智能策略**：大窗口模型（>200k）仅压缩，小窗口模型（≤200k）自动 rollover
- **自动巡检**：Cron 每 10 分钟检查，无需人工干预
- **安全收口**：HOT_MEMORY.md 追加而非覆写，不丢内容

## 安装

### 1. 复制技能目录

```bash
cp -r skills/auto-session-rollover ~/.openclaw/workspace/skills/
```

### 2. 测试运行

```bash
# 检查上下文状态
python3 ~/.openclaw/workspace/skills/auto-session-rollover/scripts/watchdog.py

# 测试 rollover（脚本自行判断是否需要执行）
python3 ~/.openclaw/workspace/skills/auto-session-rollover/scripts/rollover.py
```

### 3. 创建 Cron 巡检任务

```bash
openclaw cron add \
  --name "ctx-watchdog" \
  --every 10m \
  --session isolated \
  --light-context \
  --timeout-seconds 120 \
  --no-deliver \
  --message '你是上下文巡检守护进程。只做一件事：

1. exec: python3 ~/.openclaw/workspace/skills/auto-session-rollover/scripts/watchdog.py
2. 解析 JSON 输出
3. action 字段决定下一步：
   - healthy / already_rolled → 输出状态，结束
   - rollover_warning / compress_soft → 输出 usage_pct 警告，结束
   - rollover_required / compress_hard → exec: python3 ~/.openclaw/workspace/skills/auto-session-rollover/scripts/rollover.py → 输出结果，结束

不要做其他任何事。'
```

### 4.（可选）集成 HEARTBEAT.md

在 HEARTBEAT.md 检查项中加入退休标记检查：

```markdown
检查顺序：
1. session_status 查看上下文占用
2. 检查 memory/hot/HOT_MEMORY.md 是否有 ROLLED_OVER: true
   → 若有：提示"旧会话已退休，建议开新会话"，不回复 HEARTBEAT_OK
...
```

## 配置

编辑 `config.json` 自定义上下文窗口大小：

```json
{
  "contextWindowK": 200
}
```

| 值 | 含义 |
|---|---|
| `null` | 跟随模型官方值（从 openclaw.json 读取） |
| `200` | 锁定 200k（**推荐**，省钱） |
| `400` | 锁定 400k |
| `1048` | 锁定 1M |

### ⚠️ 超过 200k 的 API 费用提醒

大多数 API 提供商对超过 200k 的输入收取额外费用。以下为各模型**超阈值后的价格对比**（按贵→便宜排序）：

| 模型 | 最大窗口 | ≤200k Input | >200k Input | 涨幅 | ≤200k Output | >200k Output | 涨幅 |
|------|---------|-------------|-------------|------|-------------|-------------|------|
| **Claude Opus 4.6** | 1M | $5/M | $10/M | **2x** | $25/M | $37.50/M | **1.5x** |
| **Claude Sonnet 4.6** | 1M | $3/M | $6/M | **2x** | $15/M | $22.50/M | **1.5x** |
| **GPT-5.4** | 1.05M | $2.50/M | $5/M* | **2x** | $15/M | $22.50/M* | **1.5x** |
| **MiMo v2 Pro** | 1M | $1/M | $2/M | **2x** | $3/M | $6/M | **2x** |
| **MiniMax M2.7** | 204k | $0.30/M | — | — | $1.20/M | — | — |
| **GLM-5** | 200k | $0.50/M | — | — | $1.50/M | — | — |

> *GPT-5.4 阈值为 272k，超过后整次会话都按加价计费

#### 💰 一次 1M 上下文会话的成本估算

假设输入 800k tokens + 输出 50k tokens：

| 模型 | 输入费 | 输出费 | 合计 | 相对成本 |
|------|--------|--------|------|---------|
| **Claude Opus 4.6** | $8.00 | $1.88 | **$9.88** | 🔴 最贵 |
| **Claude Sonnet 4.6** | $4.80 | $1.13 | **$5.93** | 🟠 |
| **GPT-5.4** | $4.00 | $1.13 | **$5.13** | 🟡 |
| **MiMo v2 Pro** | $1.60 | $0.30 | **$1.90** | 🟢 最便宜 |

> MiMo 用满 1M 的成本只有 Claude Opus 的 **1/5**

#### 💡 建议

- **日常使用**：锁定 `200k`，绝大多数场景够用，省钱
- **超长文档/代码库**：临时调大（`null` 跟随模型），用完改回 `200k`
- **不差钱**：设 `null`，让模型跑满官方最大值

## 阈值规则

| 模型 contextWindow | 软触发 | 硬触发 | 策略 |
|---|---|---|---|
| ≤ 200k | 150k | 180k | rollover（收口+退休+续跑提示） |
| > 200k | 75% | 90% | 仅压缩旧日志 |

## 文件结构

```
auto-session-rollover/
├── README.md           ← 本文件
├── SKILL.md            ← 技能指令
└── scripts/
    ├── ctx_common.py   ← 公共模块（配置+阈值+token读取）
    ├── watchdog.py     ← 巡检脚本（JSON输出+退出码）
    └── rollover.py     ← 收口脚本（清理+记忆+退休标记）
```

## 手动操作

```bash
# 查看 cron 任务
openclaw cron list

# 手动触发巡检
openclaw cron run <job-id>

# 暂停巡检
openclaw cron edit <job-id> --disabled
```

## 依赖

- Python 3（标准库即可，无需 pip install）
- **OpenClaw 2026.3.24**（已验证兼容）
- `openclaw` CLI 在 PATH 中

## 兼容性

适用于所有 OpenClaw 安装，自动适配：
- 不同模型（自动读取 contextWindow）
- 不同平台（macOS / Linux / Windows with WSL）
- 不同会话模式（legacy 小窗口 / 大窗口 1M+）

### 与 OpenClaw 原生功能的关系

| OpenClaw 原生 | 本技能 | 关系 |
|--------------|--------|------|
| **Session Pruning** | — | ✅ 互补。Pruning 裁剪旧工具结果（per-request），本技能管理会话级生命周期 |
| **Auto Compaction** | — | ✅ 互补。Compaction 总结旧消息留在原会话，本技能退休旧会话 + 生成续跑提示 |
| **`/compact`** | — | ✅ 互补。手动压缩当前会话，不换会话 |
| **`/new` `/reset`** | — | ✅ 互补。`/new` 丢弃上下文开新会话，本技能保留续跑路径跨会话 |
| **Cron Jobs** | Watchdog | ✅ 直接使用。本技能用 OpenClaw 内置 cron 部署定时巡检 |
| **上下文阈值管理** | Rollover | ✅ 补缺。OpenClaw 无原生 rollover / session handoff 机制 |

**结论：完全兼容，无冲突。** 本技能填补的是 OpenClaw 缺少的"会话级 rollover + 续跑提示 + 自动退休标记"能力，与原生 compaction / pruning 各管各的层面。
