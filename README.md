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
- OpenClaw 2026.3.x+
- `openclaw` CLI 在 PATH 中

## 兼容性

适用于所有 OpenClaw 安装，自动适配：
- 不同模型（自动读取 contextWindow）
- 不同平台（macOS / Linux / Windows with WSL）
- 不同会话模式（legacy 小窗口 / 大窗口 1M+）
