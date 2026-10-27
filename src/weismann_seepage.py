"""
Weismann 路二 · 层3渗漏通道 (v1.0)
===================================
表观遗传跨代传递机制：让高频/重要的体细胞经验，能受控地"升级"为生殖细胞内容。
这不是自动写入（那会污染 DNA），而是：
  1. 采样：从高频体细胞记忆中，基于显著性/情感强度提取候选
  2. 提案：生成 proposal（含理由，但**不主动写入**）
  3. 审核：造物主审核通过后，才执行升级写入
  4. 存档：已处理提案进入 archive，避免重复

设计立场：
  - 渗漏 ≠ 自动写入。DNA 不应被对话直接改（见层1写保护）。
  - 渗漏 = 把"值得永久保留的经验"，以提案形式递交给决策层（造物主）。
  - 本模块只负责"采样 + 提案 + 记录"，实际升级写入由人工/授权流程执行。

数据源：
  - surface_tension_state.json 的 recent_events（情感事件流）
  - tension_queue.json（蒸馏出的 WreckageNode 矛盾）
  - cognitive_friction_registry.json（活跃认知差）

用法：
  python weismann_seepage.py            # 采样+提案（cron 调用）
  python weismann_seepage.py --review   # 列出待审提案
  python weismann_seepage.py --apply <id>  # 应用某提案（供审核后落地）
"""
import sys
import os
import json
import hashlib
import argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from datetime import datetime, timezone

WS = Path(r"C:\Users\qq366410837\.qclaw\workspace")
AGENT = WS / "_agent_memory"

PROPOSAL_FILE = AGENT / "weismann_proposals.json"
ARCHIVE_FILE = AGENT / "weismann_proposals_archive.jsonl"

MAX_PENDING = 30  # 待审上限，防堆积


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default if default is not None else {}


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_proposals() -> list:
    return _load_json(PROPOSAL_FILE, [])


def _save_proposals(proposals: list):
    _save_json(PROPOSAL_FILE, proposals)


# ─────────────────────────────────────────────────────────────
# 采样器：从各数据源提取候选体细胞经验
# ─────────────────────────────────────────────────────────────
# 系统事件类型：非真实情感，不产生提案
SYSTEM_EVENT_TYPES = {"decay_tick", "auto_restore", "baseline_refresh", "session_frozen"}

def _sample_emotions(limit=5):
    """从 recent_events 提取高情感强度事件（过滤系统噪音）"""
    st = _load_json(AGENT / "surface_tension_state.json", {})
    events = st.get("recent_events", [])
    events = [e for e in events if e.get("type") not in SYSTEM_EVENT_TYPES]
    if not events:
        return []

    def strength(ev):
        vals = []
        for k, v in ev.items():
            if isinstance(v, (int, float)) and abs(v) > 0.3 and k not in ("ts", "tick"):
                vals.append(abs(v))
        return max(vals) if vals else 0.0

    events_sorted = sorted(events, key=strength, reverse=True)
    return events_sorted[:limit]


def _sample_tensions(limit=5):
    """从 tension_queue 提取高强度矛盾节点"""
    tq = _load_json(AGENT / "tension_queue.json", {})
    nodes = tq.get("nodes", []) if isinstance(tq, dict) else []
    if not nodes:
        return []
    nodes_sorted = sorted(
        nodes,
        key=lambda n: n.get("tension_score", n.get("tension", 0.0)),
        reverse=True,
    )
    return nodes_sorted[:limit]


def _sample_frictions(limit=5):
    """从摩擦 registry 提取活跃认知差"""
    fr = _load_json(AGENT / "cognitive_friction_registry.json", {})
    frictions = []
    if isinstance(fr, dict):
        frictions = fr.get("frictions", [])
    elif isinstance(fr, list):
        frictions = fr
    if not frictions:
        return []

    def friction_score(f):
        return f.get("intensity", 0.0) if isinstance(f, dict) else 0.0

    frictions_sorted = sorted(frictions, key=friction_score, reverse=True)
    return frictions_sorted[:limit]


# ─────────────────────────────────────────────────────────────
# 提案生成
# ─────────────────────────────────────────────────────────────
def _fingerprint(item) -> str:
    """生成去重指纹：id 优先，其次内容摘要"""
    if isinstance(item, dict):
        if item.get("id"):
            return str(item["id"])
        text = json.dumps(item, ensure_ascii=False, sort_keys=True)
        return hashlib.md5(text.encode()).hexdigest()[:12]
    return str(item)[:12]


def _extract_theme(item) -> str:
    """抽主题：node.void 或事件 type"""
    if isinstance(item, dict):
        for key in ("void", "theme", "type", "category", "contradiction_type", "pattern_type"):
            v = item.get(key)
            if isinstance(v, str) and v.strip():
                return v[:60]
        for key in ("summary", "content", "description", "evidence"):
            v = item.get(key)
            if isinstance(v, str) and v.strip():
                return v[:80]
    return "未命名主题"


def _is_duplicate(proposals, fingerprint: str) -> bool:
    """防重复：同指纹已在待审或 archive"""
    for p in proposals:
        if p.get("fingerprint") == fingerprint:
            return True
    if ARCHIVE_FILE.exists():
        for line in ARCHIVE_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                a = json.loads(line)
                if a.get("fingerprint") == fingerprint:
                    return True
            except Exception:
                continue
    return False


def generate_proposals() -> list:
    """采集 + 生成提案（增量）"""
    existing = _load_proposals()
    existing_fp = {p.get("fingerprint") for p in existing}
    new_proposals = []

    # 1. 情感事件 → 提案
    for ev in _sample_emotions():
        fp = _fingerprint(ev)
        if not fp or fp in existing_fp or _is_duplicate(existing, fp):
            continue
        theme = _extract_theme(ev)
        new_proposals.append({
            "source": "emotion_flow",
            "fingerprint": fp,
            "theme": theme,
            "sentiment": "high_emotional_intensity",
            "reason": f"高情感强度事件：{theme}",
            "proposed_at": _now_iso(),
            "status": "pending",
        })

    # 2. 矛盾节点 → 提案
    for n in _sample_tensions():
        fp = _fingerprint(n)
        if not fp or fp in existing_fp or _is_duplicate(existing, fp):
            continue
        theme = _extract_theme(n)
        tension = n.get("tension_score", n.get("tension", 0.0)) if isinstance(n, dict) else 0.0
        new_proposals.append({
            "source": "tension_distill",
            "fingerprint": fp,
            "theme": theme,
            "tension_score": round(tension, 3),
            "reason": f"蒸馏出高张力矛盾（{round(tension, 2)}）：{theme}",
            "proposed_at": _now_iso(),
            "status": "pending",
        })

    # 3. 认知摩擦 → 提案
    for f in _sample_frictions():
        fp = _fingerprint(f)
        if not fp or fp in existing_fp or _is_duplicate(existing, fp):
            continue
        theme = _extract_theme(f)
        intensity = f.get("intensity", 0.0) if isinstance(f, dict) else 0.0
        new_proposals.append({
            "source": "cognitive_friction",
            "fingerprint": fp,
            "theme": theme,
            "intensity_score": round(intensity, 3),
            "reason": f"活跃认知差（强度{round(intensity, 2)}）：{theme}",
            "proposed_at": _now_iso(),
            "status": "pending",
        })

    # 合并 + 待审上限控制
    merged = existing + new_proposals
    pending = [p for p in merged if p.get("status") == "pending"]
    if len(pending) > MAX_PENDING:
        overflow = pending[:-MAX_PENDING]
        ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ARCHIVE_FILE, "a", encoding="utf-8") as f:
            for p in overflow:
                p["status"] = "overflow_archived"
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        merged = [p for p in merged if p.get("status") != "overflow_archived"]

    _save_proposals(merged)
    return new_proposals


# ─────────────────────────────────────────────────────────────
# 审核工具
# ─────────────────────────────────────────────────────────────
def review() -> int:
    """列出待审提案"""
    proposals = _load_proposals()
    pending = [p for p in proposals if p.get("status") == "pending"]
    if not pending:
        print("[weismann_seepage] 无待审提案")
        return 0
    print(f"[weismann_seepage] 待审提案 {len(pending)} 条:")
    for i, p in enumerate(pending):
        src = p.get("source")
        theme = p.get("theme", "")
        score = p.get("tension_score") or p.get("intensity_score") or p.get("sentiment") or ""
        print(f"  [{i}] ({src}) {theme} | {score} | fp={p['fingerprint']}")
    return len(pending)


def apply(pidx: int):
    """将待审提案标记为已应用。实际写入生殖细胞由层1权限流程接管。"""
    proposals = _load_proposals()
    pending = [p for p in proposals if p.get("status") == "pending"]
    if pidx < 0 or pidx >= len(pending):
        print(f"[weismann_seepage] 索引越界: {pidx}")
        return
    target = pending[pidx]
    fp = target["fingerprint"]
    for p in proposals:
        if p.get("fingerprint") == fp:
            p["status"] = "applied"
            p["applied_at"] = _now_iso()
            break
    _save_proposals(proposals)
    print(f"[weismann_seepage] applied: {target['theme']} (fp={fp})")
    print(f"  注：实际写入生殖细胞需经层1权限流程（受控升级）")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--review", action="store_true", help="列出待审提案")
    parser.add_argument("--apply", type=int, metavar="IDX", help="应用某待审提案")
    args = parser.parse_args()

    if args.review:
        review()
        return

    if args.apply is not None:
        apply(args.apply)
        return

    new = generate_proposals()
    if new:
        print(f"[weismann_seepage] 新增提案 {len(new)} 条:")
        for p in new:
            print(f"  + ({p['source']}) {p['theme']}")
    else:
        print("[weismann_seepage] 无新提案（已有内容已去重）")


if __name__ == "__main__":
    main()
