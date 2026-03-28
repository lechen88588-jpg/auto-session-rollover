#!/usr/bin/env python3
"""更深一层集成测试：验证 rollover 的幂等性与已退休场景。"""

import importlib.util
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
ROLLOVER = ROOT / 'scripts' / 'rollover.py'


def load_rollover_module():
    spec = importlib.util.spec_from_file_location('rollover_mod_idempotent', ROLLOVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def make_old_log(memory_dir: Path):
    old_name = (datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d') + '.md'
    old_log = memory_dir / old_name
    old_log.write_text('# old log\n')
    return old_log


def test_rollover_is_idempotent_when_already_marked():
    mod = load_rollover_module()
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        hot_dir = ws / 'memory' / 'hot'
        hot_dir.mkdir(parents=True, exist_ok=True)
        memory_dir = ws / 'memory'
        hot = hot_dir / 'HOT_MEMORY.md'
        next_prompt = hot_dir / 'NEXT_SESSION_PROMPT.md'

        hot.write_text(
            '# 🔥 HOT\n\n'
            '## 下一步\n'
            '- 继续验证库存同步后的刷新逻辑\n\n'
            '## ROLLOVER\n'
            '- ROLLED_OVER: true\n'
            '- ROLLOVER_TIME: 2026-03-28 18:00\n'
            '- ROLLOVER_REASON: hard_trigger (181k/200k)\n'
        )
        make_old_log(memory_dir)

        mod.WORKSPACE = ws
        mod.HOT = hot
        mod.NEXT = next_prompt
        mod.MEMORY_DIR = memory_dir
        mod.get_status = lambda: {
            'ctx_used_k': 182,
            'max_ctx_k': 200,
            'model': 'test-model',
            'mode': 'legacy',
            'need_rollover': True,
            'soft_limit_k': 150,
            'hard_limit_k': 180,
            'usage_pct': 91.0,
            'action': 'rollover_required',
        }

        before = hot.read_text()
        code = mod.run()
        after = hot.read_text()

        assert_true(code == 0, 'idempotent rollover should return 0')
        assert_true(before == after, 'existing rollover marker should not be duplicated or altered')
        assert_true(after.count('ROLLED_OVER: true') == 1, 'rollover marker should appear only once')
        assert_true(next_prompt.exists(), 'next prompt should still be generated for handoff context')


def test_legacy_healthy_should_skip_without_side_effects():
    mod = load_rollover_module()
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        hot_dir = ws / 'memory' / 'hot'
        hot_dir.mkdir(parents=True, exist_ok=True)
        memory_dir = ws / 'memory'
        hot = hot_dir / 'HOT_MEMORY.md'
        next_prompt = hot_dir / 'NEXT_SESSION_PROMPT.md'

        hot.write_text('# 🔥 HOT\n\n## 下一步\n- 保持观察\n')
        old_log = make_old_log(memory_dir)

        mod.WORKSPACE = ws
        mod.HOT = hot
        mod.NEXT = next_prompt
        mod.MEMORY_DIR = memory_dir
        mod.get_status = lambda: {
            'ctx_used_k': 120,
            'max_ctx_k': 200,
            'model': 'test-model',
            'mode': 'legacy',
            'need_rollover': True,
            'soft_limit_k': 150,
            'hard_limit_k': 180,
            'usage_pct': 60.0,
            'action': 'healthy',
        }

        before = hot.read_text()
        code = mod.run()
        after = hot.read_text()

        assert_true(code == 0, 'healthy legacy run should return 0')
        assert_true(before == after, 'healthy legacy run should not mutate hot memory')
        assert_true(not next_prompt.exists(), 'healthy legacy run should not create next prompt')
        assert_true(old_log.exists(), 'healthy legacy run should not clean logs when skipped')


def main():
    test_rollover_is_idempotent_when_already_marked()
    test_legacy_healthy_should_skip_without_side_effects()
    print('PASS: idempotency and skip-side-effect integration tests passed')


if __name__ == '__main__':
    main()
