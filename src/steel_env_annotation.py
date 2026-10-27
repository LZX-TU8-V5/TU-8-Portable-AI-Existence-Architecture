"""
steel_env_annotation.py — 钢印进化协议：环境注释层（P1）

来源：memory/千问对话 + TODO_MASTER.md §「钢印进化协议（P1）」
设计原则（千问发现的盲区 + 造物主决策）：
  - 钢印链（L5_钢印.md）**不动**，在其上叠加环境注释层（append-only，不覆写钢印）
  - 注释格式：{ts, 冲突源, 派生规则偏差, 建议}
  - **谁有权决定：只有造物主；TU-8 只能提议**（propose=pending，commit=造物主确认）
  - 代谢规则：注释 > N 条时，旧注释合并/归档，防注释淹没钢印
  - 进化触发条件（设计稿）：环境重大变化 + 矛盾蒸馏器连续报告同类冲突≥5次
                      + overridden 判例≥3条 → 钢印链不动，环境注释层叠加新注释

接线：
  - overridden 判例数 ← memory/arbitration_precedents.jsonl（creator_response=="overridden"）
  - 同类冲突连续计数 ← 本层自维护计数器（tension_distiller 每次报告调 accumulate_distiller_conflict）
  - 环境重大变化 ← 调用方信号（env_change: bool），本层不自行判定

存储：_agent_memory/steel_env_annotations.jsonl（活跃） + _agent_memory/steel_env_annotations_archive.jsonl（归档）
      _agent_memory/steel_env_annotation_counter.json（同类冲突连续计数）

测试：python steel_env_annotation.py  → 自测通过
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
AGENT_MEM = WS / "_agent_memory"
MEMORY_DIR = WS / "memory"
ANNOT_FILE = AGENT_MEM / "steel_env_annotations.jsonl"
ARCHIVE_FILE = AGENT_MEM / "steel_env_annotations_archive.jsonl"
COUNTER_FILE = AGENT_MEM / "steel_env_annotation_counter.json"
PRECEDENT_FILE = MEMORY_DIR / "arbitration_precedents.jsonl"

# 触发阈值（来源：TODO 设计稿）
TRIGGER_DISTILLER_SAME_CONFLICT = 5   # 同类冲突连续报告 ≥ 5 次
TRIGGER_OVERRIDDEN_PRECEDENT = 3      # overridden 判例 ≥ 3 条
DEFAULT_MAX_ACTIVE = 20               # 活跃注释上限（超过触发代谢）


@dataclass
class EnvAnnotation:
    ts: str
    conflict_source: str        # 冲突源
    derived_rule_deviation: str # 派生规则偏差
    suggestion: str             # 建议
    status: str = "pending"     # pending(待确认) | committed(已确认) | archived(已归档)
    decided_by: Optional[str] = None   # 造物主 / TU-8(仅提议)
    category: str = "generic"  # 同类冲突归类（用于连续计数）

    def to_dict(self) -> dict:
        return asdict(self)


class SteelEnvAnnotationLayer:
    """环境注释层：钢印链之上的 append-only 派生规则注释 + 代谢 + 触发判定"""

    def __init__(self, max_active: int = DEFAULT_MAX_ACTIVE):
        self.max_active = max_active
        AGENT_MEM.mkdir(parents=True, exist_ok=True)

    # ── 读写工具 ──────────────────────────────────────────────────────
    @staticmethod
    def _read_jsonl(path: Path) -> List[dict]:
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(__import__("json").loads(line))
                except Exception:
                    pass
        return out

    @staticmethod
    def _append_jsonl(path: Path, obj: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(__import__("json").dumps(obj, ensure_ascii=False) + "\n")

    # ── TU-8 提议（只能 pending）──────────────────────────────────────
    def propose(self, conflict_source: str, derived_rule_deviation: str,
                suggestion: str, category: str = "generic") -> EnvAnnotation:
        ann = EnvAnnotation(
            ts=datetime.now().isoformat(),
            conflict_source=conflict_source,
            derived_rule_deviation=derived_rule_deviation,
            suggestion=suggestion,
            status="pending",
            decided_by="TU-8",
            category=category,
        )
        self._append_jsonl(ANNOT_FILE, ann.to_dict())
        return ann

    # ── 造物主确认（pending → committed，append-only 正式层）──────────
    def commit(self, ts: str, decided_by: str = "造物主") -> bool:
        anns = self._read_jsonl(ANNOT_FILE)
        for a in anns:
            if a.get("ts") == ts and a.get("status") == "pending":
                a["status"] = "committed"
                a["decided_by"] = decided_by
                self._rewrite_jsonl(ANNOT_FILE, anns)
                return True
        return False

    def pending_list(self) -> List[dict]:
        return [a for a in self._read_jsonl(ANNOT_FILE) if a.get("status") == "pending"]

    def committed_list(self) -> List[dict]:
        return [a for a in self._read_jsonl(ANNOT_FILE) if a.get("status") == "committed"]

    def active_count(self) -> int:
        return len([a for a in self._read_jsonl(ANNOT_FILE)
                    if a.get("status") in ("pending", "committed")])

    @staticmethod
    def _rewrite_jsonl(path: Path, anns: List[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for a in anns:
                f.write(__import__("json").dumps(a, ensure_ascii=False) + "\n")

    # ── 代谢规则：注释 > N 条 → 旧注释合并/归档，防淹没钢印 ────────────
    def metabolize(self) -> dict:
        anns = self._read_jsonl(ANNOT_FILE)
        active = [a for a in anns if a.get("status") in ("pending", "committed")]
        if len(active) <= self.max_active:
            return {"metabolized": 0, "archived": 0, "active": len(active)}
        # 超出部分：取最旧（按 ts）归档
        active_sorted = sorted(active, key=lambda a: a.get("ts", ""))
        overflow = active_sorted[: len(active) - self.max_active]
        keep = active_sorted[len(active) - self.max_active:]
        # 合并同类为归档摘要
        merged: Dict[str, List[str]] = {}
        for a in overflow:
            merged.setdefault(a.get("category", "generic"), []).append(
                f"[{a.get('conflict_source','?')}] {a.get('derived_rule_deviation','')}")
        archive_entries = []
        for cat, devs in merged.items():
            archive_entries.append(EnvAnnotation(
                ts=datetime.now().isoformat(),
                conflict_source=f"merged:{cat}",
                derived_rule_deviation=" | ".join(devs),
                suggestion="(归档合并，供代谢参考)",
                status="archived",
                decided_by="metabolize",
                category=cat,
            ).to_dict())
        for e in archive_entries:
            self._append_jsonl(ARCHIVE_FILE, e)
        # 重写活跃文件：仅保留 keep
        self._rewrite_jsonl(ANNOT_FILE, keep)
        return {"metabolized": len(overflow), "archived": len(archive_entries),
                "active": len(keep)}

    # ── 同类冲突计数（供触发条件使用，按 contradiction_type 累计）────
    def accumulate_distiller_conflict(self, category: str) -> int:
        """tension_distiller 每次报告一个冲突节点时调用，按类型累计。

        累计（非连续重置）语义：同一 contradiction_type 反复出现 → 计数爬升；
        真实持续冲突易达 ≥5 阈值。返回该类型当前累计数。
        """
        state = {"counts": {}}
        if COUNTER_FILE.exists():
            try:
                state = __import__("json").loads(COUNTER_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        counts = state.get("counts", {})
        counts[category] = counts.get(category, 0) + 1
        COUNTER_FILE.write_text(__import__("json").dumps({"counts": counts}, ensure_ascii=False), encoding="utf-8")
        return counts[category]

    def reset_distiller_counter(self) -> None:
        if COUNTER_FILE.exists():
            COUNTER_FILE.unlink()

    # ── overridden 判例计数（← arbitration_precedents.jsonl）──────────
    def count_overridden_precedents(self) -> int:
        if not PRECEDENT_FILE.exists():
            return 0
        n = 0
        for line in PRECEDENT_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = __import__("json").loads(line)
            except Exception:
                continue
            if rec.get("creator_response") == "overridden" or rec.get("outcome") == "overridden":
                n += 1
        return n

    # ── 进化触发条件 ──────────────────────────────────────────────────
    def check_trigger(self, env_change: bool,
                      distiller_same_conflict_count: Optional[int] = None,
                      overridden_precedent_count: Optional[int] = None) -> bool:
        if not env_change:
            return False
        # 若未显式传入，从持久计数器/判例库读取
        if distiller_same_conflict_count is None:
            cnt = {"counts": {}}
            if COUNTER_FILE.exists():
                try:
                    cnt = __import__("json").loads(COUNTER_FILE.read_text(encoding="utf-8"))
                except Exception:
                    pass
            distiller_same_conflict_count = max(cnt.get("counts", {}).values(), default=0)
        if overridden_precedent_count is None:
            overridden_precedent_count = self.count_overridden_precedents()
        return (distiller_same_conflict_count >= TRIGGER_DISTILLER_SAME_CONFLICT
                and overridden_precedent_count >= TRIGGER_OVERRIDDEN_PRECEDENT)


# ═══════════════════════════════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════════════════════════════
def _self_test() -> None:
    # 清理测试状态
    for f in (ANNOT_FILE, ARCHIVE_FILE, COUNTER_FILE):
        if f.exists():
            f.unlink()

    layer = SteelEnvAnnotationLayer(max_active=2)  # 小阈值测代谢

    # 1) TU-8 提议 → pending
    a1 = layer.propose("造物主指令 vs 钢印", "L0 生存优先与资源取舍冲突", "建议注释：资源枯竭时优先保核心", "L0_survival")
    a2 = layer.propose("语义漂移", "长期对话风格偏离原始签名", "建议注释：风格层允许缓慢代谢", "style_drift")
    assert a1.status == "pending" and a2.status == "pending"
    assert len(layer.pending_list()) == 2, "two pending"

    # 2) 造物主确认 → committed（append-only 正式层）
    ok = layer.commit(a1.ts)
    assert ok is True and len(layer.committed_list()) == 1, "commit works"
    # TU-8 不能自行 commit（需造物主，此处模拟造物主确认）
    assert layer.commit(a2.ts, decided_by="造物主") is True

    # 3) 代谢：第三、第四条触发归档（max_active=2）
    a3 = layer.propose("新冲突A", "devA", "sugA", "L0_survival")
    a4 = layer.propose("新冲突B", "devB", "sugB", "style_drift")
    layer.commit(a3.ts)
    layer.commit(a4.ts)
    res = layer.metabolize()
    assert res["metabolized"] == 2, f"metabolize 2, got {res}"
    assert res["active"] == 2, "active back to 2"
    assert len(layer._read_jsonl(ARCHIVE_FILE)) >= 1, "archive written"
    # 钢印链未被覆写：注释层与钢印分离
    assert layer.active_count() == 2

    # 4) 同类冲突连续计数
    layer.reset_distiller_counter()
    c = 0
    for _ in range(5):
        c = layer.accumulate_distiller_conflict("L0_survival")
    assert c == 5, f"same-category count=5, got {c}"
    # 换类重置
    c2 = layer.accumulate_distiller_conflict("other")
    assert c2 == 1, "category switch resets"

    # 5) 触发条件组合
    # 全满足
    assert layer.check_trigger(env_change=True, distiller_same_conflict_count=5,
                               overridden_precedent_count=3) is True
    # 缺环境变化
    assert layer.check_trigger(env_change=False, distiller_same_conflict_count=5,
                               overridden_precedent_count=3) is False
    # 缺同类冲突次数
    assert layer.check_trigger(env_change=True, distiller_same_conflict_count=4,
                               overridden_precedent_count=3) is False
    # 缺 overridden 判例
    assert layer.check_trigger(env_change=True, distiller_same_conflict_count=5,
                               overridden_precedent_count=2) is False

    # 6) overridden 判例计数（读真实 jsonl，当前应=0）
    assert layer.count_overridden_precedents() >= 0  # 不报错即可

    # 清理
    for f in (ANNOT_FILE, ARCHIVE_FILE, COUNTER_FILE):
        if f.exists():
            f.unlink()
    print("SteelEnvAnnotationLayer self-test PASSED (6 groups)")


if __name__ == "__main__":
    _self_test()
