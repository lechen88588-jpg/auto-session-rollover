#!/usr/bin/env python3
"""集成测试：验证 rollover 主流程在 legacy / large-window 两种模式下的行为。"""

import importlib.util
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
ROLLOVER = ROOT / 'scripts' / 'rollover.py'


def load_rollover_module():
    spec = importlib.util.spec_from_file_location('rollover_mod_integration', ROLLOVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_legacy_rollover():
    mod = load_rollover_module()
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        hot_dir = ws / 'memory' / 'hot'
        hot_dir.mkdir(parents=True, exist_ok=True)
        hot = hot_dir / 'HOT_MEMORY.md'
        next_prompt = hot_dir / 'NEXT_SESSION_PROMPT.md'
        memory_dir = ws / 'memory'

        # 新结构 HOT_MEMORY
        hot.write_text(
            '# 🔥 HOT\n\n'
            '## 当前状态\n'
            '- 正在处理库存同步问题\n\n'
            '## 下一步\n'
            '- 继续验证库存同步后的刷新逻辑\n'
        )

        # 3 天前旧日志（应被清理）
        old_name = (datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d') + '.md'
        old_log = memory_dir / old_name
        old_log.write_text('# old log\n')

        mod.WORKSPACE = ws
        mod.HOT = hot
        mod.NEXT = next_prompt
        mod.MEMORY_DIR = memory_dir
        mod.get_status = lambda: {
            'ctx_used_k': 181,
            'max_ctx_k': 200,
            'model': 'test-model',
            'mode': 'legacy',
            'need_rollover': True,
            'soft_limit_k': 150,
            'hard_limit_k': 180,
            'usage_pct': 90.5,
            'action': 'rollover_required',
        }

        code = mod.run()
        assert_true(code == 0, 'legacy rollover should return 0')
        assert_true(next_prompt.exists(), 'NEXT_SESSION_PROMPT.md should be created')
        prompt_text = next_prompt.read_text()
        assert_true('继续验证库存同步后的刷新逻辑' in prompt_text, 'next step should be written into prompt')

        hot_text = hot.read_text()
        assert_true('ROLLED_OVER: true' in hot_text, 'hot memory should contain rollover marker')
        assert_true('V4.3-external-scheduler' in hot_text, 'hot memory should contain rollover mode')
        assert_true(not old_log.exists(), 'old daily log should be removed in legacy rollover')


def test_large_window_compress_only():
    mod = load_rollover_module()
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        hot_dir = ws / 'memory' / 'hot'
        hot_dir.mkdir(parents=True, exist_ok=True)
        hot = hot_dir / 'HOT_MEMORY.md'
        next_prompt = hot_dir / 'NEXT_SESSION_PROMPT.md'
        memory_dir = ws / 'memory'

        hot.write_text('# 🔥 HOT\n\n## 下一步\n- 保持观察\n')

        old_name = (datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d') + '.md'
        old_log = memory_dir / old_name
        old_log.write_text('# old log\n')

        mod.WORKSPACE = ws
        mod.HOT = hot
        mod.NEXT = next_prompt
        mod.MEMORY_DIR = memory_dir
        mod.get_status = lambda: {
            'ctx_used_k': 780,
            'max_ctx_k': 1048,
            'model': 'test-model-large',
            'mode': 'large_window',
            'need_rollover': False,
            'soft_limit_k': 786,
            'hard_limit_k': 943,
            'usage_pct': 74.4,
            'action': 'healthy',
        }

        code = mod.run()
        assert_true(code == 0, 'compress-only should return 0')
        assert_true(not next_prompt.exists(), 'compress-only should not create NEXT_SESSION_PROMPT.md')
        hot_text = hot.read_text()
        assert_true('ROLLED_OVER: true' not in hot_text, 'compress-only should not append rollover marker')
        assert_true(not old_log.exists(), 'old daily log should be removed in compress-only mode')


def main():
    test_legacy_rollover()
    test_large_window_compress_only()
    print('PASS: integration rollover flow works for legacy and large-window modes')


if __name__ == '__main__':
    main()
