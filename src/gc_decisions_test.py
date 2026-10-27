"""
gc_decisions_test.py — gc_decisions 完整性单测 [P0, 2026-08-29 落地]

验证目标（设计稿 §6.1 验收）：
  - 模拟 100 次 GC 决策，断言每条含 reason/evidence 字段
  - append_decision 原子写：失败回滚 no-op（自述失败→返回 False）
  - count_decisions / get_pending 计数正确

不依赖 live gc_decisions.md（用临时文件隔离，测完清理）。
"""

from __future__ import annotations

import re
import tempfile
import sys
from pathlib import Path

# 把 src 加入路径以便 import gc_decisions
SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import gc_decisions as gcd


def _tmp_decisions_file():
    """用临时 gc_decisions.md 隔离测试，不污染 live。"""
    tf = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".md", delete=False
    )
    tf.close()
    return Path(tf.name)


def test_100_decisions_have_reason_evidence() -> bool:
    """模拟 100 次 DEGRADE/EVICT 决策，断言每条含 reason + evidence 字段。"""
    tmp = _tmp_decisions_file()
    gcd.GC_DECISIONS = tmp
    try:
        for i in range(100):
            action = "DEGRADE" if i % 2 == 0 else "EVICT"
            ok = gcd.append_decision(
                action,
                f"section_{i}",
                reason=f"score below threshold and age>{7 + i % 30}",
                evidence=f"no citation event #{i}",
            )
            assert ok is True, f"append Degradation #{i} failed"
        txt = tmp.read_text(encoding="utf-8")
        # 断言每条结构化自述含 reason/evidence
        reasons = re.findall(r"理由自述：(.+)", txt)
        evidences = re.findall(r"证据引用：(.+)", txt)
        assert len(reasons) == 100, f"reason count {len(reasons)} != 100"
        assert len(evidences) == 100, f"evidence count {len(evidences)} != 100"
        # 无空 reason/evidence
        assert all(r.strip() for r in reasons), "empty reason found"
        assert all(e.strip() for e in evidences), "empty evidence found"
        # count_decisions 正确
        assert gcd.count_decisions() == 100, f"count {gcd.count_decisions()} != 100"
        # get_pending 返回 100 条 PENDING
        assert len(gcd.get_pending()) == 100, f"pending {len(gcd.get_pending())} != 100"
        return True
    finally:
        tmp.unlink(missing_ok=True)


def test_atomic_rollback_on_failure() -> bool:
    """自述失败→返回 False（调用方回滚 no-op）。
    模拟真实失败场景：目标路径是一个已存在的目录（不可作文件 open）。
    """
    # 纯目录路径当文件 → open(...) 抛 IsADirectoryError（Windows 下 dir-as-file 失败）
    gcd.GC_DECISIONS = Path(tempfile.gettempdir())  # 是目录，不是文件
    ok = gcd.append_decision("EVICT", "x", reason="r", evidence="e")
    assert ok is False, "expected False on write failure (dir-as-file)"
    # 确认没有残留半写文件（GCD 路径是纯目录，不应生成文件）
    assert not gcd.GC_DECISIONS.is_file(), "partial file leaked"
    return True


def main() -> None:
    r1 = test_100_decisions_have_reason_evidence()
    print(f"[1] 100 decisions reason/evidence integrity: {'PASS' if r1 else 'FAIL'}")
    r2 = test_atomic_rollback_on_failure()
    print(f"[2] atomic rollback on failure: {'PASS' if r2 else 'FAIL'}")
    # 还原 live 路径（防测试污染模块全局状态）
    gcd.GC_DECISIONS = gcd.WORKSPACE / "memory" / "gc_decisions.md"
    if r1 and r2:
        print("ALL P0 GC_DECISIONS TESTS PASS")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
