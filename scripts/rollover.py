#!/usr/bin/env python3
"""
Auto Session Rollover V4.3
- 大窗口模型：仅压缩日志，不 rollover
- Legacy 模型：收口 → 退休标记 → 生成续跑提示
- 适配精简后的 HOT_MEMORY 结构
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
import re

# 同目录导入公共模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ctx_common import get_status, HOT, WORKSPACE

NEXT = WORKSPACE / 'memory/hot/NEXT_SESSION_PROMPT.md'
MEMORY_DIR = WORKSPACE / 'memory'


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


def extract_next_step(text: str) -> str:
    """兼容新旧 HOT_MEMORY 结构提取下一步"""
    lines = text.splitlines()

    # 新结构：## 下一步
    for i, line in enumerate(lines):
        if line.strip() == '## 下一步':
            for j in range(i + 1, min(i + 6, len(lines))):
                cand = lines[j].strip()
                if cand.startswith('- '):
                    return cand[2:].strip()

    # 旧结构：## 下一步第一动作
    for i, line in enumerate(lines):
        if line.strip() == '## 下一步第一动作':
            for j in range(i + 1, min(i + 6, len(lines))):
                cand = lines[j].strip()
                if cand.startswith('- '):
                    return cand[2:].strip()

    return '读取当前热记忆后，按老板最新指令继续'


def run():
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

    # ── 大窗口模式：只做压缩 ──
    if not need_rollover:
        removed = clean_old_logs()
        result = {
            'version': 'V4.3',
            'mode': 'compress-only',
            'model_max_ctx_k': max_ctx_k,
            'runtime_mode': mode,
            'need_rollover': need_rollover,
            'soft_limit_k': soft_k,
            'hard_limit_k': hard_k,
            'context_k': ctx_k,
            'usage_pct': st['usage_pct'],
            'removed_logs': removed,
            'removed_count': len(removed),
            'action': action,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # ── Legacy 模式：检查是否需要 rollover ──
    if action not in ('rollover_required', 'compress_hard'):
        result = {
            'version': 'V4.3',
            'mode': 'skip',
            'action': action,
            'message': '未达到硬触发，跳过',
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # ── 清理旧日志 ──
    removed = clean_old_logs()

    # ── 从现有 HOT_MEMORY 提取下一步（只读，不覆写）──
    old = HOT.read_text() if HOT.exists() else ''
    next_step = extract_next_step(old)

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
    rollover_marker = f'''\n\n## ROLLOVER
- ROLLED_OVER: true
- ROLLOVER_TIME: {now_str}
- ROLLOVER_REASON: hard_trigger ({ctx_k}k/{max_ctx_k}k)
- ROLLOVER_MODEL: {model}
- ROLLOVER_MODE: V4.3-external-scheduler
'''

    marker_appended = False
    if HOT.exists():
        content = HOT.read_text()
        if 'ROLLED_OVER: true' not in content:
            content += rollover_marker
            HOT.write_text(content)
            marker_appended = True
    else:
        HOT.write_text(f'# 🔥 HOT\n{rollover_marker}')
        marker_appended = True

    result = {
        'version': 'V4.3',
        'mode': 'rollover',
        'model_max_ctx_k': max_ctx_k,
        'runtime_mode': mode,
        'need_rollover': need_rollover,
        'soft_limit_k': soft_k,
        'hard_limit_k': hard_k,
        'context_k': ctx_k,
        'usage_pct': st['usage_pct'],
        'action': action,
        'removed_logs': removed,
        'removed_count': len(removed),
        'next_prompt': str(NEXT),
        'next_step': next_step,
        'rollover_marker_appended': marker_appended,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
