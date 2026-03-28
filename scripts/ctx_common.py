#!/usr/bin/env python3
"""
Auto Session Rollover — 公共模块
提供：配置读取、阈值计算、会话 token 读取
被 watchdog.py 和 rollover.py 共同引用

用户可通过 config.json 自定义 contextWindow（见 README.md）
"""

import json, os, subprocess, sys
from pathlib import Path

# ── 路径（标准 OpenClaw 目录结构，可被环境变量覆盖）──
WORKSPACE = Path(os.environ.get('OPENCLAW_WORKSPACE', str(Path.home() / '.openclaw/workspace'))).expanduser()
CONFIG = Path(os.environ.get('OPENCLAW_CONFIG', str(Path.home() / '.openclaw/openclaw.json'))).expanduser()
HOT = WORKSPACE / 'memory/hot/HOT_MEMORY.md'
STATE_FILE = WORKSPACE / 'memory/hot/watchdog-state.json'
SKILL_DIR = Path(__file__).resolve().parent.parent  # auto-session-rollover/
USER_CONFIG = SKILL_DIR / 'config.json'
MAIN_SESSION_KEY = 'agent:main:main'


def read_user_config():
    """读取用户自定义配置（技能目录下的 config.json）"""
    if not USER_CONFIG.exists():
        return {}
    try:
        return json.loads(USER_CONFIG.read_text())
    except Exception:
        return {}


def read_model_config():
    """从 openclaw.json 读取主模型名称和 contextWindow
    优先使用用户在 config.json 中的 override 设置
    """
    user_cfg = read_user_config()
    override_k = user_cfg.get('contextWindowK')

    model_name = 'unknown'
    max_ctx_k = 200

    # 1. 尝试从 openclaw.json 读取模型官方值
    try:
        cfg = json.loads(CONFIG.read_text())
        primary = cfg.get('agents', {}).get('defaults', {}).get('model', {}).get('primary', '')
        providers = cfg.get('models', {}).get('providers', {})
        if '/' in primary:
            provider_name, model_id = primary.split('/', 1)
            model_name = model_id
            provider = providers.get(provider_name, {})
            for m in provider.get('models', []):
                if m.get('id') == model_id and 'contextWindow' in m:
                    max_ctx_k = m['contextWindow'] // 1000
                    break
    except Exception as e:
        print(f"WARN: config read error: {e}", file=sys.stderr)

    # 2. 用户 override（如果设置且 ≤ 模型官方值）
    if override_k is not None:
        override_k = int(override_k)
        if override_k <= max_ctx_k:
            max_ctx_k = override_k
        else:
            print(f"WARN: contextWindowK ({override_k}k) exceeds model max ({max_ctx_k}k), using model max", file=sys.stderr)

    return model_name, max_ctx_k


def calc_thresholds(max_ctx_k):
    """根据模型 contextWindow 计算动态阈值
    返回 (soft_k, hard_k, mode, need_rollover)
    
    - legacy (≤200k): 软150k/硬180k，需要 rollover
    - large_window (>200k): 软75%/硬90%，仅压缩不 rollover
    """
    if max_ctx_k <= 200:
        return 150, 180, 'legacy', True
    return int(max_ctx_k * 0.75), int(max_ctx_k * 0.90), 'large_window', False


def read_ctx_usage():
    """从 openclaw sessions --json 读取主会话 token 使用量（单位 k）"""
    try:
        result = subprocess.run(
            ['openclaw', 'sessions', '--json'],
            capture_output=True, text=True, timeout=15
        )
        lines = [l for l in result.stdout.split('\n') if not l.strip().startswith('[plugins]')]
        data = json.loads('\n'.join(lines))
        for s in data.get('sessions', []):
            if s.get('key') == MAIN_SESSION_KEY:
                total = s.get('totalTokens', 0) or 0
                return total // 1000
    except Exception as e:
        print(f"WARN: sessions read error: {e}", file=sys.stderr)
    return 0


def is_already_rolled():
    """检查 HOT_MEMORY.md 是否已有退休标记"""
    if not HOT.exists():
        return False
    return 'ROLLED_OVER: true' in HOT.read_text()


def read_last_state():
    """读取上次 watchdog 状态（防重复触发）"""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state):
    """保存 watchdog 状态"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def get_status():
    """一站式获取完整状态，返回 dict"""
    model_name, max_ctx_k = read_model_config()
    soft_k, hard_k, mode, need_rollover = calc_thresholds(max_ctx_k)
    ctx_used_k = read_ctx_usage()
    rolled = is_already_rolled()

    soft_triggered = ctx_used_k >= soft_k
    hard_triggered = ctx_used_k >= hard_k

    action = 'healthy'
    if rolled:
        action = 'already_rolled'
    elif hard_triggered:
        action = 'rollover_required' if need_rollover else 'compress_hard'
    elif soft_triggered:
        action = 'rollover_warning' if need_rollover else 'compress_soft'

    return {
        'model': model_name,
        'max_ctx_k': max_ctx_k,
        'mode': mode,
        'need_rollover': need_rollover,
        'soft_limit_k': soft_k,
        'hard_limit_k': hard_k,
        'ctx_used_k': ctx_used_k,
        'usage_pct': round(ctx_used_k / max_ctx_k * 100, 1) if max_ctx_k > 0 else 0,
        'soft_triggered': soft_triggered,
        'hard_triggered': hard_triggered,
        'already_rolled': rolled,
        'action': action,
    }
