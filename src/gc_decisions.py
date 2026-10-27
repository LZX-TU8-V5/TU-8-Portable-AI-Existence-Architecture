"""
gc_decisions.py — 元认知监督：GC 遗忘理由结构化自述（PROMOTE 设计稿 §3）

哲学硬绑定（§3）：
  - 自述生成与状态变更（DEGRADE/EVICT 动作）必须在同一事务内完成。
  - 若自述生成失败 → DEGRADE/EVICT 动作回滚，保持 no-op 安全态（反思不可后置补写）。
  - 实现：GC 决策先写 gc_decisions 条目（含 reason/evidence），成功后再执行动作；异常则整段回滚。

验收（§6.1）：
  - 每次 EVICT/DEGRADE 必有结构化自述（reason/evidence 字段）
  - no-op 回归：_evict_section 当前为 no-op，本模块只记录不删

H 级变更：2026-08-27 落地（造物主 2026-08-26 签字后）。
"""

import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WORKSPACE = Path(os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace"))
GC_DECISIONS = WORKSPACE / "memory" / "gc_decisions.md"

# 结构化自述模板（§3.1）
TEMPLATE = (
    "### {ts} | 动作={action} 段=\"{section}\"\n"
    "- 理由自述：{reason}\n"
    "- 证据引用：{evidence}\n"
    "- 复核标记：{review}\n"
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_decision(action: str, section: str, reason: str,
                    evidence: str = "", review: str = "PENDING") -> bool:
    """
    原子追加一条 GC 决策自述到 gc_decisions.md。
    返回 True=写入成功；False=失败（调用方须回滚对应动作到 no-op）。
    """
    try:
        block = TEMPLATE.format(
            ts=_now_utc(),
            action=action,
            section=section[:80],
            reason=reason[:300],
            evidence=evidence[:300] or "（无显式引用事件）",
            review=review,
        )
        # 原子写：先落临时文件，再 append，避免半截写入
        GC_DECISIONS.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(GC_DECISIONS.parent),
            suffix=".tmp", delete=False
        ) as tf:
            tf.write(block)
            tmp_path = tf.name
        # 追加到主文件（append 本身对单条是原子的）
        with open(GC_DECISIONS, "a", encoding="utf-8") as f:
            f.write("\n" + block)
        os.unlink(tmp_path)
        return True
    except Exception as e:
        # 自述失败 → 返回 False，调用方负责回滚动作
        print(f"[GC_DECISIONS] 自述写入失败，动作须回滚 no-op: {e}")
        return False


def count_decisions() -> int:
    """返回 gc_decisions.md 中结构化条目数（供集成测试断言）。"""
    if not GC_DECISIONS.exists():
        return 0
    txt = GC_DECISIONS.read_text(encoding="utf-8")
    # 统计 '### ' 开头的条目头（带 动作= 字段）
    return len(re.findall(r"^### .*动作=(EVICT|DEGRADE)", txt, re.MULTILINE))


def get_pending() -> list[str]:
    """返回 PENDING 条目段标题（供 dream_check 回溯反哺 PROMOTE）。
    修正（2026-08-29）：原正则逐行匹配 ### 行不含「复核标记」→ 永远 0；
    改为跨条块 finditer(re.DOTALL) 匹配整块。
    """
    if not GC_DECISIONS.exists():
        return []
    txt = GC_DECISIONS.read_text(encoding="utf-8")
    out = []
    # 按条块分割（每条以 ### 开头），块内匹配段名 + PENDING 标记
    for block in re.split(r"(?=### )", txt):
        if "复核标记：PENDING" in block:
            m = re.search(r"段=\"(.+?)\"", block)
            if m:
                out.append(m.group(1))
    return out


if __name__ == "__main__":
    ok = append_decision("DEGRADE", "测试段_自述联调", "score 低于阈值且 age>7天", "无引用事件")
    print("append_decision:", ok, "| count:", count_decisions())
    print("pending:", get_pending())
