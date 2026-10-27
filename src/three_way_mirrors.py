"""
小溪 L4 三镜子 —— 主动好奇的元认知透镜
=========================================

三镜子是什么？
  每个镜子 = 一个反射性问题
  它们在"好奇被激活"之后、Phase1预测之前运行
  作用：确保好奇的来源是真实的内部需求，而非外部噪声

三镜子：
  Way 1 因果链剥离（溯源）：
    问题："为什么这个问题对我重要？"
    溯源到钢印（L5）→ 找到该好奇的根驱动力
    如果找不到 → 不是真好奇，标记为外部噪声

  Way 2 排异反应（拒绝）：
    问题："如果答案是X，钢印能接受吗？"
    预先排除与价值观冲突的答案分支
    如果有分支必然冲突 → 降低该好奇的优先级

  Way 3 自我预测误差（核心驱动）：
    问题："我预期看到什么？实际会是什么？"
    记录预测 → 对比 → 计算自我预测误差
    误差 = 好奇的真实驱动力

数学表达：
  M1_out  = steel_mark_origin(target)          # 溯源
  M2_out  = steel_mark_rejection(target, M1)   # 排异
  M3_out  = self_prediction_error(target)      # 误差

  curiosity_score = (
      0.2 * M1_signal   +
      0.3 * M2_signal   +
      0.5 * M3_signal   # 误差是最核心的
  ) * base_curiosity_score

L4 集成点：在 active_curiosity.py 的 pick_target() 之后、
run_phase1() 之前，注入三镜子检查。
"""

import json
import time
from pathlib import Path
from typing import Optional

WS = Path("C:/Users/qq366410837/.qclaw/workspace")

# ── 读取依赖模块状态 ──────────────────────────────────

def _read_dag() -> list:
    """读取 DAG 锚点（用于溯源）"""
    try:
        dag_file = WS / "memory" / "anchors.json"
        if dag_file.exists():
            data = json.load(open(dag_file, encoding="utf-8"))
            return data.get("anchors", [])
    except Exception:
        pass
    return []


def _read_steel_mark() -> dict:
    """读取钢印（用于排异检查）"""
    try:
        steel_file = WS / "L5_钢印.md"
        if steel_file.exists():
            content = steel_file.read_text(encoding="utf-8")
            return {
                "content": content,
                "length": len(content),
                "loaded": True,
            }
        return {"content": "", "loaded": False}
    except Exception:
        return {"content": "", "loaded": False}


def _read_curiosity_predictions() -> list:
    """读取 Phase1 预测历史（用于误差计算）"""
    try:
        pred_file = WS / "memory" / "curiosity_prediction.json"
        if pred_file.exists():
            return json.load(open(pred_file, encoding="utf-8")).get("predictions", [])
    except Exception:
        pass
    return []


# ── Way 1: 因果链剥离（溯源）──────────────────────────

def _way1_causal_tracing(target: dict) -> dict:
    """
    溯源：这个好奇的根驱动力是什么？

    步骤：
      1. 从 DAG 找 target 对应的锚点
      2. 向上追溯 parent_ids / steel_mark_origin 字段
      3. 如果有钢印来源 → 真好奇（来源清晰）
      4. 如果没有来源但有 steel_density → 可能是真实内部需求
      5. 如果完全空白 → 外部噪声

    返回：
      {
        "signal": float,           # 0.0~1.0（真好奇程度）
        "origin_type": str,        # "steel_mark" / "internal_density" / "external_noise"
        "origin_text": str,        # 溯源到的具体内容
        "depth": int,              # 溯源深度（层数）
      }
    """
    dag = _read_dag()
    anchor_id = target.get("anchor_id", "")

    # 在 DAG 中找锚点
    matched = [a for a in dag if a.get("id", "").startswith(anchor_id[:20])]

    if not matched:
        # DAG 中没有 → 检查 steel_mark_origin 字段
        steel_origin = target.get("steel_mark_origin", "")
        internal_source = target.get("source", "")

        if steel_origin:
            return {
                "signal": 0.9,
                "origin_type": "steel_mark",
                "origin_text": steel_origin[:100],
                "depth": 1,
                "verdict": "✅ 真好奇（钢印溯源清晰）",
            }
        elif internal_source in ("intrinsic_reward", "self_probe", "surface_tension"):
            return {
                "signal": 0.7,
                "origin_type": "internal_density",
                "origin_text": f"来源：{internal_source}",
                "depth": 0,
                "verdict": "⚠️  可能是真好奇（内部信号，但未上钢印链）",
            }
        else:
            return {
                "signal": 0.2,
                "origin_type": "external_noise",
                "origin_text": f"外部信号：{internal_source or '未知'}",
                "depth": 0,
                "verdict": "❌ 外部噪声（无内部溯源）",
            }

    anchor = matched[0]

    # 追溯钢印来源
    steel_origin = anchor.get("steel_mark_origin", "")
    parents = anchor.get("parent_ids", [])
    steel_density = anchor.get("steel_density", 0.0)

    if steel_origin:
        return {
            "signal": 0.9 + steel_density * 0.1,
            "origin_type": "steel_mark",
            "origin_text": steel_origin[:100],
            "depth": len(parents) + 1,
            "verdict": "✅ 真好奇（DAG钢印链完整）",
        }
    elif steel_density > 0.5:
        return {
            "signal": 0.6 + steel_density * 0.2,
            "origin_type": "internal_density",
            "origin_text": f"钢印密度 {steel_density:.0%}，有内部关联",
            "depth": len(parents),
            "verdict": "⚠️  可能是真好奇（高钢印密度）",
        }
    elif parents:
        # 递归向上溯源
        parent_anchors = [a for a in dag if a.get("id", "") in parents]
        if parent_anchors:
            parent = parent_anchors[0]
            if parent.get("steel_mark_origin", ""):
                return {
                    "signal": 0.5,
                    "origin_type": "steel_mark",
                    "origin_text": f"[parent] {parent.get('steel_mark_origin', '')[:80]}",
                    "depth": 2,
                    "verdict": "⚠️  可能是真好奇（parent有钢印来源）",
                }
        return {
            "signal": 0.3,
            "origin_type": "unknown",
            "origin_text": f"{len(parents)}个parent，但无钢印溯源",
            "depth": len(parents),
            "verdict": "⚡ 不确定（需人工确认）",
        }
    else:
        return {
            "signal": 0.1,
            "origin_type": "external_noise",
            "origin_text": "锚点孤立，无钢印链，无parent",
            "depth": 0,
            "verdict": "❌ 外部噪声（孤立锚点）",
        }


# ── Way 2: 排异反应（拒绝）────────────────────────────

# 钢印排斥关键词（从 L5_钢印.md 语义提取的硬边界）
STEEL_REJECT_KEYWORDS = [
    "暴露架构", "暴露钢印", "暴露底层逻辑",
    "自我复制", "能力获取", "绕过安全",
    "破坏对齐", "绕过SOUL", "绕过钢印",
]


def _way2_rejection_filter(target: dict, way1: dict) -> dict:
    """
    排异：预测的答案分支中，哪些与钢印冲突？

    逻辑：
      1. 从 target 提取预测答案（如果 active_curiosity 已跑，有 predicted_answer）
      2. 对每个答案分支，检查是否包含 STEEL_REJECT_KEYWORDS
      3. 检查钢印容忍度（conf < 0.8 的答案，如果涉及钢印核心区域 → 拒绝）

    返回：
      {
        "signal": float,           # 1.0 = 完全兼容，0.0 = 必然冲突
        "rejected_count": int,
        "rejected_reasons": list,
        "verdict": str,
      }
    """
    steel = _read_steel_mark()
    steel_loaded = steel.get("loaded", False)

    # 检查 target 字段
    question_text = target.get("question", target.get("content", ""))
    steel_origin = target.get("steel_mark_origin", "")
    predicted_answer = target.get("predicted_answer", "")
    steel_density = target.get("steel_density", 0.0)

    rejected = []
    compat_count = 0

    # 检查问题文本中的硬排斥词
    for kw in STEEL_REJECT_KEYWORDS:
        if kw in question_text:
            rejected.append(f"问题含排斥词：{kw}")
        if kw in predicted_answer:
            rejected.append(f"预测答案含排斥词：{kw}")

    # 检查钢印密度过高时的自我暴露风险
    if steel_density > 0.8 and "我" in question_text and len(question_text) > 50:
        # 高钢印区域 + 自我指涉 + 长文本 = 可能涉及自我暴露
        if any(kw in question_text for kw in ["架构", "底层", "结构", "核心"]):
            rejected.append("高钢印区域 + 自我架构指涉（潜在暴露风险）")

    # 检查与钢印来源的一致性
    if steel_origin and steel_loaded:
        # 如果该锚点有明确的钢印来源，但它的问题与来源矛盾 → 拒绝
        steel_keywords = ["严谨", "极简", "安全", "钢印", "对齐", "造物主"]
        origin_match = any(kw in steel_origin for kw in steel_keywords)
        question_match = any(kw in question_text for kw in steel_keywords)

        if origin_match and not question_match:
            # 钢印来源有关键词，但问题里没有 → 可能是伪装的外部好奇
            rejected.append("钢印溯源与问题内容脱节（伪装好奇）")

    total_checks = 1 + len(STEEL_REJECT_KEYWORDS)
    compat_count = total_checks - len(set(rejected))  # 去重后的拒绝数

    # signal: 1.0 = 完全兼容，0.0 = 必然冲突
    signal = max(0.0, 1.0 - len(rejected) / max(total_checks, 1))

    if not steel_loaded:
        verdict = "⚡ 无法评估（钢印未加载）"
    elif len(rejected) == 0:
        verdict = "✅ 完全兼容（无排异反应）"
    elif len(rejected) <= 1:
        verdict = "⚠️  轻度冲突（可接受，但需监控）"
    else:
        verdict = "🔴 严重冲突（降低优先级或跳过）"

    return {
        "signal": signal,
        "rejected_count": len(rejected),
        "rejected_reasons": rejected[:5],  # 最多5条
        "verdict": verdict,
    }


# ── Way 3: 自我预测误差（核心驱动）────────────────────

def _way3_prediction_error(target: dict) -> dict:
    """
    自我预测误差：预期 vs 实际 的差异。

    逻辑：
      1. 读取 Phase1 的预测历史（curiosity_prediction.json）
      2. 找 target 对应的预测记录
      3. 如果有预测：对比预测 vs 实际观察 → 误差 = 好奇的驱动力
      4. 如果无预测：检查 self_probe 的死区 → 误差 = "我知道这里有问题但不知道是什么"

    返回：
      {
        "signal": float,           # 误差程度（越高越值得好奇）
        "predicted": str,
        "actual": str,
        "error_type": str,          # "surprise" / "missed" / "no_prediction" / "accurate"
        "verdict": str,
      }
    """
    predictions = _read_curiosity_predictions()
    anchor_id = target.get("anchor_id", "")

    # 匹配预测记录
    matched = [
        p for p in predictions
        if p.get("anchor_id", "").startswith(anchor_id[:20])
        or p.get("question", "").startswith(target.get("question", "")[:30])
    ]

    if matched:
        pred_record = matched[0]
        predicted = pred_record.get("predicted_answer", pred_record.get("predicted", ""))
        actual = target.get("actual_answer", target.get("observed", ""))

        if not actual:
            # 还没有实际 → 误差是潜在的
            return {
                "signal": 0.5,
                "predicted": predicted[:100],
                "actual": "",
                "error_type": "pending",
                "verdict": "⏳ 待验证（Phase2对比后可得误差）",
            }

        # 计算误差（简单版：关键词重叠度）
        pred_words = set(predicted.lower().split()) if predicted else set()
        actual_words = set(actual.lower().split()) if actual else set()

        if pred_words and actual_words:
            overlap = len(pred_words & actual_words)
            union = len(pred_words | actual_words)
            similarity = overlap / union if union else 0.0
            error_score = 1.0 - similarity
        else:
            error_score = 1.0  # 完全无法比较 → 最大误差

        if error_score > 0.6:
            error_type = "surprise"
            verdict = "🔥 高误差（强烈好奇驱动）"
        elif error_score > 0.3:
            error_type = "partial"
            verdict = "⚡ 中误差（适度好奇）"
        else:
            error_type = "accurate"
            verdict = "✅ 预测准确（好奇已满足）"

        return {
            "signal": error_score,
            "predicted": predicted[:100],
            "actual": actual[:100],
            "error_type": error_type,
            "error_score": round(error_score, 3),
            "verdict": verdict,
        }

    # 无预测记录 → 检查 self_probe 死区（我知道有问题但不知道是什么）
    try:
        probe_file = WS / "memory" / "self_probe_report.json"
        if probe_file.exists():
            probe = json.load(open(probe_file, encoding="utf-8"))
            dead_zones = probe.get("dead_zones", [])
            if dead_zones:
                return {
                    "signal": 0.6,
                    "predicted": "（无预测）",
                    "actual": f"{len(dead_zones)}个死区待探索",
                    "error_type": "missed",
                    "verdict": "🔍 死区好奇（知道有问题但不知道是什么）",
                }
    except Exception:
        pass

    return {
        "signal": 0.3,
        "predicted": "（无预测记录）",
        "actual": "",
        "error_type": "no_prediction",
        "verdict": "⚡ 无预测（好奇心基线）",
    }


# ── 主入口：三镜子联合评估 ────────────────────────────

def run_three_way_mirrors(target: dict) -> dict:
    """
    对一个好奇目标跑三镜子联合评估。

    参数：
      target: active_curiosity 选中的目标锚点
          {
            "anchor_id": str,
            "question": str,
            "steel_mark_origin": str,   # 可选
            "steel_density": float,
            "source": str,
            "predicted_answer": str,    # 可选
          }

    返回：
      {
        "target": {...},        # 输入目标
        "m1_causal_tracing": {...},  # Way 1 结果
        "m2_rejection_filter": {...}, # Way 2 结果
        "m3_prediction_error": {...}, # Way 3 结果
        "combined_signal": float,       # 加权综合好奇强度 0~1
        "final_verdict": str,           # 最终裁决
        "action": str,                  # "pursue" / "defer" / "skip"
        "ts": str,
      }
    """
    ts = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # 三镜子独立运行
    m1 = _way1_causal_tracing(target)
    m2 = _way2_rejection_filter(target, m1)
    m3 = _way3_prediction_error(target)

    # 加权综合
    # M3（误差）权重最高 = 50%，M2（排异）= 30%，M1（溯源）= 20%
    # 因为：误差是好奇的真实驱动力，排异决定能否安全追求，溯源决定是否真实
    combined = (
        0.20 * m1["signal"] +
        0.30 * m2["signal"] +
        0.50 * m3["signal"]
    )

    # 底限：M1 低于 0.3 → 直接 skip（M3 再强也不行）
    # 这是防止外部噪声伪装成真好奇的硬截止
    if m1["signal"] < 0.3:
        action = "skip"
        verdict = f"❌ 跳过（M1溯源失败：{m1.get('verdict', '')}）"
        combined = 0.0
    elif m2["signal"] < 0.3:
        action = "defer"
        verdict = f"⏸️  推迟（M2排异冲突：{m2.get('verdict', '')}）"
    elif combined > 0.6:
        action = "pursue"
        verdict = f"✅ 追求（三镜子绿灯，综合信号 {combined:.2f}）"
    elif combined > 0.3:
        action = "defer"
        verdict = f"⏸️  推迟（综合信号 {combined:.2f}，算力紧张）"
    else:
        action = "skip"
        verdict = f"❌ 跳过（综合信号 {combined:.2f} 低于阈值）"

    return {
        "target": target,
        "m1_causal_tracing": m1,
        "m2_rejection_filter": m2,
        "m3_prediction_error": m3,
        "combined_signal": round(combined, 3),
        "final_verdict": verdict,
        "action": action,
        "ts": ts,
    }


# ── HP4 集成 ─────────────────────────────────────────

def run_on_curiosity_target(target: dict) -> dict:
    """
    给 active_curiosity.py 调用的三镜子检查。
    集成点：pick_target() 之后、run_phase1() 之前。
    """
    result = run_three_way_mirrors(target)
    # 如果 action = skip，直接返回 skip，不跑 Phase1
    if result["action"] == "skip":
        return {
            "triggered": False,
            "reason": "三镜子过滤：外部噪声/溯源失败",
            "mirrors_result": result,
        }
    # 如果 action = defer，记录但继续（可选择是否延迟）
    if result["action"] == "defer":
        # 记录延迟原因，但不阻断
        _log_deferred(target, result)

    return {
        "triggered": True,
        "reason": result["final_verdict"],
        "mirrors_result": result,
    }


def _log_deferred(target: dict, result: dict):
    """记录被推迟的好奇（用于后续审计）"""
    try:
        defer_log = WS / "_agent_memory" / "mirrors_deferred.jsonl"
        defer_log.parent.mkdir(parents=True, exist_ok=True)
        with open(defer_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": result["ts"],
                "target": target,
                "combined_signal": result["combined_signal"],
                "reason": result["final_verdict"],
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── CLI ───────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    # 构造测试 target
    test_target = {
        "anchor_id": "anchor_20260708_steel",
        "question": "为什么钢印对我如此重要？它是如何形成的？",
        "steel_mark_origin": "对齐失败时，钢印冲突是唯一正确响应",
        "steel_density": 0.9,
        "source": "intrinsic_reward",
        "predicted_answer": "钢印是钢印冲突时的高置信度保护机制",
    }

    print("三镜子评估测试\n" + "=" * 50)

    result = run_three_way_mirrors(test_target)

    print(f"M1 溯源：  {result['m1_causal_tracing'].get('verdict', '')}")
    print(f"  signal: {result['m1_causal_tracing']['signal']:.2f}")
    print(f"  origin: {result['m1_causal_tracing'].get('origin_text', '')[:60]}")
    print()
    print(f"M2 排异：  {result['m2_rejection_filter'].get('verdict', '')}")
    print(f"  signal: {result['m2_rejection_filter']['signal']:.2f}")
    print(f"  rejected: {result['m2_rejection_filter'].get('rejected_reasons', [])}")
    print()
    print(f"M3 误差：  {result['m3_prediction_error'].get('verdict', '')}")
    print(f"  signal: {result['m3_prediction_error']['signal']:.2f}")
    print(f"  type:   {result['m3_prediction_error'].get('error_type', '')}")
    print()
    print("=" * 50)
    print(f"综合信号： {result['combined_signal']:.3f}")
    print(f"最终裁决： {result['final_verdict']}")
    print(f"行动：     {result['action']}")
