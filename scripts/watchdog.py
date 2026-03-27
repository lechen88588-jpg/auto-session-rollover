#!/usr/bin/env python3
"""
Session Context Watchdog
由 OpenClaw cron job 每 10 分钟调用。
输出 JSON 状态 + 退出码（0=健康 / 1=软触发 / 2=硬触发）
"""

import json, sys
from pathlib import Path
from datetime import datetime

# 同目录导入公共模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ctx_common import get_status, read_last_state, save_state

# ── 获取状态 ──
status = get_status()
action = status['action']

# ── 构建输出 ──
last = read_last_state()
last_action = last.get('action', 'none')

result = {
    'timestamp': datetime.now().isoformat(),
    **status,
    'last_action': last_action,
    'state_changed': action != last_action,
}

# ── 输出 ──
print(json.dumps(result, ensure_ascii=False, indent=2))

# ── 保存状态 ──
save_state(result)

# ── 退出码 ──
if action in ('rollover_required', 'compress_hard'):
    sys.exit(2)
elif action in ('rollover_warning', 'compress_soft'):
    sys.exit(1)
else:
    sys.exit(0)
