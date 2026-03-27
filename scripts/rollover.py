#!/usr/bin/env python3
"""
Auto Session Rollover V4.2
- 大窗口模型：仅压缩日志，不 rollover
- Legacy 模型：收口 → 退休标记 → 生成续跑提示
- HOT_MEMORY.md 追加而非覆写
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import re

# 同目录导入公共模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ctx_common import get_status, HOT

WORKSPACE = Path.home() / '.openclaw/workspace'
NEXT = WORKSPACE / 'memory/hot/NEXT_SESSION_PROMPT.md'
MEMORY_DIR = WORKSPACE / 'memory'

# ── 获取状态 ──
st = get_status()
ctx_k = st['ctx_used_k']
max_ctx_k = st['max_ctx_k']
model = st['model']
mode = st['mode']
need_rollover = st['need_rollover']
soft_k = st['soft_limit_k']
hard_k = st['hard_limit_k']
action = st['action']


def clean_old_logs():
    """清理 3 天前的 daily logs（幂等）"""
    now = datetime.now()
    cutoff = now - timedelta(days=3)
    removed = []
    for p in MEMORY_DIR.glob('20??-??-??.md'):
        m = re.match(r'(\d{4}-\d{2}-\d{2})\.md$', p.name)
        if not m:
            continue
        d = datetime.strptime(m.group(1), '%Y-%m-%d')
        if d < cutoff:
            p.unlink(missing_ok=True)
            removed.append(p.name)
    return removed


# ── 大窗口模式：只做压缩 ──
if not need_rollover:
    removed = clean_old_logs()
    print('=== AUTO SESSION ROLLOVER V4.2 (compress-only) ===')
    print('model_max_ctx_k=', max_ctx_k)
    print('mode=', mode)
    print('need_rollover=', need_rollover)
    print('soft_limit_k=', soft_k)
    print('hard_limit_k=', hard_k)
    print('context_k=', ctx_k)
    print('usage_pct=', st['usage_pct'])
    print('removed_logs=', removed)
    print('removed_count=', len(removed))
    sys.exit(0)

# ── Legacy 模式：检查是否需要 rollover ──
if action not in ('rollover_required', 'compress_hard'):
    print('=== AUTO SESSION ROLLOVER V4.2 (skip) ===')
    print('action=', action, '— 未达到硬触发，跳过')
    sys.exit(0)

# ── 清理旧日志 ──
removed = clean_old_logs()

# ── 从现有 HOT_MEMORY 提取信息（只读，不覆写）──
old = HOT.read_text() if HOT.exists() else ''
project = '当前任务'
completed = []
unfinished = []
next_step = '读取 NEXT_SESSION_PROMPT.md 后继续'

for line in old.splitlines():
    if '当前任务' in line or line.startswith('## ERP'):
        project = line.replace('## ', '').strip()
        break

for line in old.splitlines():
    if line.startswith('- '):
        if '待验证' in line or '未完成' in line or '待用户' in line:
            unfinished.append(line)
        elif any(kw in line for kw in ['✅', '已通过', '已完成', '收口完成']):
            completed.append(line)

lines = old.splitlines()
for i, line in enumerate(lines):
    if line.strip() == '## 下一步第一动作':
        for j in range(i + 1, min(i + 6, len(lines))):
            cand = lines[j].strip()
            if cand.startswith('- '):
                next_step = cand[2:].strip()
                break
        break

# ── 生成 NEXT_SESSION_PROMPT.md ──
next_prompt = f'''# NEXT SESSION PROMPT

先读：
1. MEMORY.md
2. memory/warm/WARM_MEMORY.md
3. memory/hot/HOT_MEMORY.md

当前状态：未完成，强制截断（{ctx_k}k / {max_ctx_k}k）

续跑路径：{next_step}

下一步：{next_step}

验收：
- 不重复已完成工作
- 从当前阶段继续跑
'''
NEXT.write_text(next_prompt)

# ── 追加 ROLLOVER 退休标记（不覆写已有内容）──
now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
rollover_marker = f'''

## ROLLOVER
- ROLLED_OVER: true
- ROLLOVER_TIME: {now_str}
- ROLLOVER_REASON: hard_trigger ({ctx_k}k/{max_ctx_k}k)
- ROLLOVER_MODEL: {model}
- ROLLOVER_MODE: V4.2-external-scheduler
'''

if HOT.exists():
    content = HOT.read_text()
    if 'ROLLED_OVER: true' not in content:
        content += rollover_marker
        HOT.write_text(content)
else:
    HOT.write_text(f'# 🔥 HOT - 当前会话状态\n{rollover_marker}')

print('=== AUTO SESSION ROLLOVER V4.2 ===')
print('model_max_ctx_k=', max_ctx_k)
print('mode=', mode)
print('need_rollover=', need_rollover)
print('soft_limit_k=', soft_k)
print('hard_limit_k=', hard_k)
print('context_k=', ctx_k)
print('usage_pct=', st['usage_pct'])
print('action=', action)
print('removed_logs=', removed)
print('removed_count=', len(removed))
print('next_prompt=', str(NEXT))
print('next_step=', next_step)
print('rollover_marker_appended=', True)
