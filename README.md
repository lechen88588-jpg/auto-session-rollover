# Auto Session Rollover

OpenClaw 长会话上下文治理技能：动态阈值监控、自动清理旧日志、legacy 小窗口模型自动 rollover。

## 功能

- 自动读取模型 `contextWindow`
- 小窗口模型（≤200k）：硬触发时 rollover
- 大窗口模型（>200k）：仅压缩，不 rollover
- 生成 `NEXT_SESSION_PROMPT.md`
- 在 `HOT_MEMORY.md` 追加退休标记，而不是覆写内容

## 文件结构

```text
auto-session-rollover/
├── README.md
├── SKILL.md
├── config.json
└── scripts/
    ├── ctx_common.py
    ├── watchdog.py
    └── rollover.py
```

## 安装

```bash
cp -r skills/auto-session-rollover ~/.openclaw/workspace/skills/
```

可选环境变量：

- `OPENCLAW_WORKSPACE`：覆盖默认工作区路径
- `OPENCLAW_CONFIG`：覆盖默认 `openclaw.json` 路径

## 手动测试

```bash
# 检查上下文状态
python3 ~/.openclaw/workspace/skills/auto-session-rollover/scripts/watchdog.py

# 执行收口（脚本会自行判断是否需要 rollover）
python3 ~/.openclaw/workspace/skills/auto-session-rollover/scripts/rollover.py
```

## 配置

编辑 `config.json`：

```json
{
  "contextWindowK": 200
}
```

说明：
- `null`：跟随模型官方值
- `200`：锁定 200k
- `400`：锁定 400k
- `1048`：锁定 1M

## 阈值规则

| 模型 contextWindow | 软触发 | 硬触发 | 策略 |
|---|---|---|---|
| ≤ 200k | 150k | 180k | rollover |
| > 200k | 75% | 90% | 仅压缩旧日志 |

## 运行结果

### `watchdog.py`
输出 JSON 状态，并返回退出码：
- `0`：健康 / 已退休
- `1`：软触发
- `2`：硬触发

### `rollover.py`
- 大窗口模式：仅清理 3 天前日志
- 小窗口模式：生成续跑提示，并追加 `ROLLED_OVER: true` 标记
- 输出 JSON 结果，便于 cron 或 agent 集成

## 与记忆文件的关系

- `memory/hot/HOT_MEMORY.md`：读取当前热记忆并追加退休标记
- `memory/hot/NEXT_SESSION_PROMPT.md`：生成下一会话续跑提示
- `memory/YYYY-MM-DD.md`：清理 3 天前的旧日志

## 最小回归测试

```bash
python3 tests/test_extract_next_step.py
python3 tests/test_rollover_integration.py
python3 tests/test_rollover_idempotency.py
```

当前测试覆盖：
- 精简版 `HOT_MEMORY.md`（新结构）
- 旧版 `HOT_MEMORY.md`（legacy 结构）
- 两种结构都必须正确提取“下一步”
- legacy 模式下生成 `NEXT_SESSION_PROMPT.md` 并追加退休标记
- large-window 模式下仅压缩旧日志，不生成 prompt、不追加退休标记
- 已退休场景下不重复追加退休标记（幂等）
- legacy 健康状态下跳过且不产生副作用

## 说明

- 当前运行时模型、上下文窗口与状态，以 `session_status` / OpenClaw 实际配置为准
- 如 OpenClaw CLI 或 cron 接口版本有差异，请以本地帮助和当前版本文档为准
