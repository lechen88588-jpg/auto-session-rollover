#!/usr/bin/env python3
"""最小回归测试：验证 rollover.py 对新旧 HOT_MEMORY 结构都能正确提取下一步。"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLLOVER = ROOT / 'scripts' / 'rollover.py'
FIXTURES = ROOT / 'tests' / 'fixtures'


def load_extract_next_step():
    spec = importlib.util.spec_from_file_location('rollover_mod', ROLLOVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.extract_next_step


def main():
    extract_next_step = load_extract_next_step()

    cases = [
        ('hot_memory_new.md', '继续验证库存同步后的刷新逻辑'),
        ('hot_memory_legacy.md', '继续验证库存同步后的刷新逻辑'),
    ]

    failures = []
    for name, expected in cases:
        text = (FIXTURES / name).read_text()
        got = extract_next_step(text)
        if got != expected:
            failures.append({'file': name, 'expected': expected, 'got': got})

    if failures:
        print('FAIL')
        for item in failures:
            print(item)
        sys.exit(1)

    print('PASS: extract_next_step works for new and legacy HOT_MEMORY formats')


if __name__ == '__main__':
    main()
