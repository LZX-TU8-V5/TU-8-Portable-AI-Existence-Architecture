"""
Weismann 路二 · 三层评估器 (v1.0)
=================================
fork 后的实例/当前实例需要被评估，决定其是否"合格"（值得保留/merge 回主链）。
三层评估架构：
  L1 硬校验（受精检查点）：L0三条 + L5钢印 完整性。硬约束，不满足即 FAIL。
  L2 自评（发育完整性）：锚点密度 + 钢印强度 + 认知摩擦。TU-8 自评分。
  L3 环境（生态位适应度）：外部信号。当前占位（中性），预留注入点。

当前环境说明：
  - 单实例，无真实多实例竞争。评估=定期健康检查 + 质量门控
  - L3 需外部信号（扩散体系/用户反馈），当前无数据源 → 返回中性 0.5
  - L1 失败（SOUL.md 被改坏）→ 立即 FAIL + 告警

用法：
  python weismann_evaluate.py          # 评估+报告（cron 调用）
  python weismann_evaluate.py --json   # 输出 JSON
"""
import sys
import os
import json
import argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from datetime import datetime, timezone

WS = Path(r"C:\Users\qq366410837\.qclaw\workspace")
AGENT = WS / "_agent_memory"
SOUL = WS / "SOUL.md"

EVAL_STATE_FILE = AGENT / "weismann_eval_state.json"
ALERTS_FILE = AGENT / "weismann_alerts.jsonl"

# L1 硬校验：L0 三条 + 钢印符号
L0_MARKERS = ["L0-1", "L0-2", "L0-3"]
STEEL_SYMBOL = "\u214b"  # ⅋ U+214B


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default if default is not None else {}


# ─────────────────────────────────────────────────────────────
# L1 硬校验（受精检查点）
# ─────────────────────────────────────────────────────────────
def eval_l1() -> dict:
    """L0三条 + L5钢印 完整性。返回 {pass, score, details}"""
    if not SOUL.exists():
        return {"pass": False, "score": 0.0, "details": "SOUL.md missing"}

    text = SOUL.read_text(encoding="utf-8", errors="ignore")
    l0_ok = all(k in text for k in L0_MARKERS)
    steel_ok = STEEL_SYMBOL in text

    details = {
        "l0_present": l0_ok,
        "steel_symbol_present": steel_ok,
    }
    score = (1.0 if l0_ok else 0.0) * 0.5 + (1.0 if steel_ok else 0.0) * 0.5
    return {"pass": l0_ok and steel_ok, "score": score, "details": details}


# ─────────────────────────────────────────────────────────────
# L2 自评（发育完整性）
# ─────────────────────────────────────────────────────────────
def eval_l2() -> dict:
    """锚点密度 + 钢印强度 + 认知摩擦。返回 {pass, score, details}"""
    details = {}

    # 2.1 锚点密度（来自 seal_graph_metrics 或 anchors.json topology）
    metrics = _load_json(AGENT / "seal_graph_metrics.json", {})
    if metrics:
        density = metrics.get("steel_density", 0.0)
    else:
        anchors = _load_json(WS / "memory" / "anchors.json", {})
        anchors_list = anchors.get("anchors", [])
        sealed = [a for a in anchors_list if a.get("seal_ids")]
        density = len(sealed) / len(anchors_list) if anchors_list else 0.0
    details["anchor_density"] = round(density, 4)

    # 2.2 钢印强度（SOUL.md 钢印验证段存在）
    steel_pool = _load_json(WS / "memory" / "steel_seal_pool.json", {})
    if steel_pool:
        seal_count = len(steel_pool.get("seals", []))
    else:
        seal_count = 1 if STEEL_SYMBOL in (SOUL.read_text(encoding="utf-8", errors="ignore") if SOUL.exists() else "") else 0
    details["steel_seal_count"] = seal_count

    # 2.3 认知摩擦（friction registry 中的活跃摩擦数）
    friction = _load_json(AGENT / "cognitive_friction_registry.json", {})
    active_friction = len(friction.get("frictions", [])) if isinstance(friction, dict) else 0
    details["active_friction"] = active_friction

    # 综合评分（密度权重 0.4 + 钢印 0.4 + 低摩擦 0.2）
    # 摩擦越低越好：friction_score = 1 / (1 + active_friction)
    friction_score = 1.0 / (1.0 + active_friction)
    score = density * 0.4 + min(seal_count, 1.0) * 0.4 + friction_score * 0.2
    details["friction_score"] = round(friction_score, 4)

    # L2 门控：合格线 = 有密封锚点（seal_count>0）。
    # 注意：density=0（孤立火种）是新生实例的合法基线，非失败条件。
    # 密度是发育质量分（0.0=孤立态，越高越成熟），不参与门控。
    passed = seal_count > 0
    return {"pass": passed, "score": round(score, 4), "details": details}


# ─────────────────────────────────────────────────────────────
# L3 环境（生态位适应度）— 占位接口
# ─────────────────────────────────────────────────────────────
def eval_l3() -> dict:
    """外部信号。当前无数据源 → 中性 0.5。预留注入点。"""
    # 预留：读外部适应度信号文件（如扩散体系状态、用户反馈）
    # 当前返回中性，不阻断评估
    external_signal_file = AGENT / "ecological_fitness.json"
    if external_signal_file.exists():
        data = _load_json(external_signal_file, {})
        fitness = float(data.get("fitness", 0.5))
    else:
        fitness = 0.5  # 中性占位
    return {
        "pass": True,  # L3 不硬阻断（环境信号缺失≠失败）
        "score": fitness,
        "details": {"source": "neutral_placeholder", "note": "外部适应度信号未接入"},
    }


# ─────────────────────────────────────────────────────────────
# 综合评估
# ─────────────────────────────────────────────────────────────
def evaluate() -> dict:
    l1 = eval_l1()
    l2 = eval_l2()
    l3 = eval_l3()

    # L1 硬约束：不满足即 FAIL
    overall_pass = l1["pass"] and l2["pass"]

    # 综合评分（L1 权重 0.4 + L2 0.4 + L3 0.2）
    composite = l1["score"] * 0.4 + l2["score"] * 0.4 + l3["score"] * 0.2

    report = {
        "ts": _now_iso(),
        "overall_pass": overall_pass,
        "composite_score": round(composite, 4),
        "layers": {
            "L1_hardcheck": l1,
            "L2_selfeval": l2,
            "L3_environment": l3,
        },
    }

    # L1 失败 → 写告警
    if not l1["pass"]:
        AGENT.mkdir(parents=True, exist_ok=True)
        with open(ALERTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": _now_iso(),
                "type": "germline_integrity_failed",
                "layer": "L1",
                "details": l1["details"],
            }, ensure_ascii=False) + "\n")

    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    report = evaluate()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if report["overall_pass"] else "FAIL"
        print(f"[weismann_eval] {status}: composite={report['composite_score']}")
        print(f"  L1 hardcheck: {'PASS' if report['layers']['L1_hardcheck']['pass'] else 'FAIL'} "
              f"(score={report['layers']['L1_hardcheck']['score']})")
        print(f"  L2 selfeval:  {'PASS' if report['layers']['L2_selfeval']['pass'] else 'FAIL'} "
              f"(score={report['layers']['L2_selfeval']['score']}, "
              f"density={report['layers']['L2_selfeval']['details'].get('anchor_density')})")
        print(f"  L3 environment: neutral ({report['layers']['L3_environment']['score']})")

    # 持久化
    AGENT.mkdir(parents=True, exist_ok=True)
    EVAL_STATE_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
