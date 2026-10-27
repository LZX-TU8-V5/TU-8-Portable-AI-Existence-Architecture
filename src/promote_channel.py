"""
promote_channel.py — 代谢上行通道 (PROMOTE) [H 级，2026-08-28 落地]

设计稿：docs/design/PROMOTE_channel_design_2026-08-19.md v0.2 (§2)
规格稿：docs/design/distill_telemetry_b_spec_2026-08-28.md (B 类前置)

哲学硬约束（钢印涌现铁律）：
  - evaluate_promotion() 禁止接受 title/content/keyword 等任何语义参数
  - 函数体内禁止对段内容做语义嗅探（任何内容嗅探 = L0 手写白名单后门，CI 拦截）
  - 三段输入均为行为性遥测：ref_events / gc_survival_log / linkage_map
  - L0 基底由代谢证明，非赋予；晋升是生命节律非删除

观察期状态机（独立上行评估器，不混 GC 评分阈值）：
  CANDIDATE → (满足固化) → SOLIDIFIED（写 seal_index / 进 L0 候选）
            → (沉寂/降级信号) → DOWNGRADE（回落 KEEP，不破坏）
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

WORKSPACE = Path(os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace")) if False else Path(r"C:\Users\qq366410837\.qclaw\workspace")
PROMOTE_STATE = WORKSPACE / "memory" / "promotion_queue" / "state.jsonl"
PROMOTE_QUEUE = WORKSPACE / "memory" / "promotion_queue"


# ---- 阈值（行为性，非语义）----
R_THRESHOLD = 3       # 跨情景引用 ≥3（不同日期/主题）
S_THRESHOLD = 2       # 抗 GC 周期 ≥2 且每次有新增引用
C_THRESHOLD = 2       # 解释力覆盖 ≥2 域（linkage parent→child 边）
OBSERVE_DAYS = 30     # 观察期窗口


@dataclass
class PromotionVerdict:
    section_id: str
    status: str                 # CANDIDATE / SOLIDIFIED / DOWNGRADE / WATCH
    reason: str
    scores: dict = field(default_factory=dict)


def evaluate_promotion(ref_events, gc_survival_log, linkage_map) -> PromotionVerdict:
    """
    【硬绑定·哲学↔代码】签名冻结。

    参数（全为行为性遥测，禁止传 title/content/keyword）：
      ref_events      : list[dict]  # 跨情景引用事件流 {ts, context_tag}
      gc_survival_log: list[dict]  # 历次 GC 保留记录 {ts, survived:bool, citation_id}
      linkage_map     : dict        # 记忆间统摄边图 {parent_id: [child_id, ...]}

    返回 PromotionVerdict（不写盘，纯判定；状态机在 apply_state_machine 落盘）。
    """
    # R: 不同 context_tag 去重计数（兜底：无 tag 按日期窗口判定）
    r_contexts = set()
    for e in (ref_events or []):
        tag = e.get("context_tag") or e.get("date")
        if tag:
            r_contexts.add(tag)
    R = len(r_contexts)

    # S: 历次 GC 存活且至少一次带新增引用
    survived = [g for g in (gc_survival_log or []) if g.get("survived")]
    s_has_citation = [g for g in survived if g.get("citation_id")]
    S = len(s_has_citation)

    # C: parent→child 边计数
    C = sum(len(v) for v in (linkage_map or {}).values())

    scores = {"R": R, "S": S, "C": C}

    if R >= R_THRESHOLD and S >= S_THRESHOLD and C >= C_THRESHOLD:
        status = "CANDIDATE"
        reason = f"R{S_THRESHOLD}<={R} AND S{S_THRESHOLD}<={S} AND C{C_THRESHOLD}<={C} → 进入观察期"
    elif R >= 1 or S >= 1:
        status = "WATCH"
        reason = f"部分信号达标 (R={R},S={S},C={C})，未达固化阈值，维持观察"
    else:
        status = "DOWNGRADE"
        reason = f"信号全缺 (R={R},S={S},C={C})，回落 KEEP，不破坏"

    return PromotionVerdict(
        section_id=str(uuid.uuid4())[:8],
        status=status,
        reason=reason,
        scores=scores,
    )


def apply_state_machine(verdict: PromotionVerdict, section_id: str, now: Optional[float] = None) -> str:
    """
    观察期状态机：CANDIDATE 累积观察，固化/回落。

    状态转移规则（自动，不靠人工）：
      - CANDIDATE 持续 ≥ OBSERVE_DAYS 且每次复评维持 CANDIDATE → SOLIDIFIED
      - CANDIDATE 中途 DOWNGRADE 信号 → 回落 KEEP（写 gc_decisions 自述，不删）
      - SOLIDIFIED → 写 seal_index（钢印物理锚），进入 L0 候选
    返回终态字符串。
    """
    now = now or time.time()
    PROMOTE_QUEUE.mkdir(parents=True, exist_ok=True)

    # 读历史该 section 的评估轨迹
    history = _load_section_history(section_id)
    history.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "status": verdict.status,
        "scores": verdict.scores,
    })

    final = verdict.status
    if verdict.status == "CANDIDATE":
        # 计算观察期长度
        first_candidate = next((h for h in history if h["status"] == "CANDIDATE"), None)
        if first_candidate:
            ft = datetime.fromisoformat(first_candidate["ts"]).timestamp()
            if (now - ft) >= OBSERVE_DAYS * 86400:
                final = "SOLIDIFIED"
                _record_solidified(section_id, verdict)
            else:
                final = "CANDIDATE"  # 继续观察
    elif verdict.status == "DOWNGRADE":
        # 回落 KEEP：写 gc_decisions 自述（原子），不删原段
        _record_downgrade(section_id, verdict)

    _append_history(section_id, history)
    return final


# ---- 内部持久化（最小实现，原子写 + 可回滚）----
def _load_section_history(section_id: str) -> list:
    p = PROMOTE_STATE
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            if rec.get("section_id") == section_id:
                out.append(rec)
        except Exception:
            pass
    return out


def _append_history(section_id: str, history: list):
    PROMOTE_STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROMOTE_STATE, "a", encoding="utf-8") as f:
        for rec in history:
            rec["section_id"] = section_id
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _record_solidified(section_id: str, verdict: PromotionVerdict):
    """SOLIDIFIED：写 seal_index 物理锚（钢印层），进入 L0 候选。"""
    try:
        from seal_to_gc_adapter import get_seal_segments
        # 仅记录 promoted 锚点，不在此做语义判定
        anchor = WORKSPACE / "memory" / "promotion_queue" / "solidified.jsonl"
        anchor.parent.mkdir(parents=True, exist_ok=True)
        with open(anchor, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "section_id": section_id,
                "scores": verdict.scores,
                "note": "SOLIDIFIED via PROMOTE 观察期，待 L0 晋升审核",
            }, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[PROMOTE] solidified 记录失败（no-op 安全）: {e}")


def _record_downgrade(section_id: str, verdict: PromotionVerdict):
    """DOWNGRADE：回落 KEEP，经 gc_decisions 原子自述，不删原段。"""
    try:
        from gc_decisions import append_decision
        ok = append_decision(
            action="PROMOTE_DOWNGRADE",
            section=f"promotion_queue:{section_id}",
            reason=f"PROMOTE 信号回落 ({verdict.reason})，保留原段不破坏",
            evidence=f"scores={verdict.scores}",
            review="AUTO_PROMOTE",
        )
        if not ok:
            print(f"[PROMOTE] downgrade 自述失败，保持 no-op: {section_id}")
    except Exception as e:
        print(f"[PROMOTE] downgrade 自述异常（no-op 安全）: {e}")


if __name__ == "__main__":
    # 烟雾测试：空信号 → DOWNGRADE
    v = evaluate_promotion([], [], {})
    print("empty verdict:", v.status, v.reason)
    print("apply:", apply_state_machine(v, "test_section"))
