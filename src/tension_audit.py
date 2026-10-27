"""
tension_audit.py — P1-TensionStep2：张力混合审核器

来源：千问对话 2026-07-22（来自 ARCHITECTURE_LOG.md）
设计者：造物主 × TU-8 × 千问三方对话

核心原则：
  审核标准 = 张力（非正确性）
  正确性是派生策略，结构性张力才是真正的守卫

张力混合公式：
  T_final = T_step1 + T_step2
  T_step2 ∈ [0, 0.3]，只能加，不能减

设计哲学：
  - Step1（O(1)规则）：快速锚定初始张力值
  - Step2（LLM语义）：补充规则算不出的隐含张力，只能加不能减
  - 理由：规则能算"表面张力"，LLM能感知"语义张力"；但LLM也可能被说服，
    所以Step2只能强化，不能削弱Step1的判断。
"""

import json
import time
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
SURFACE_STATE = WS / "_agent_memory" / "surface_tension_state.json"
AUDIT_LOG = WS / "_agent_memory" / "tension_audit_log.jsonl"


# ─────────────────────────────────────────────────────────────────────────────
# Step1：张力快速规则（O(1)，无LLM）
# ─────────────────────────────────────────────────────────────────────────────

# 学习类型 × 初始张力基线
LEARNING_TYPE_TENSION = {
    # 高张力：结构性冲突，需要解构重建
    "conflict_resolution":    0.80,
    "ontology_repair":       0.85,
    "steel_evolution":       0.90,
    "value_reconstruction":  0.75,
    # 中张力：认知摩擦，需要适应
    "uncertainty_resolution": 0.50,
    "belief_update":         0.55,
    "insight":               0.40,
    "contradiction_processing": 0.60,
    # 低张力：日常学习
    "habit_formation":       0.10,
    "skill_acquisition":     0.20,
    "fact_learned":          0.15,
    "preference_update":     0.25,
    "contextual_adjustment": 0.30,
    "pattern_recognition":   0.35,
    "general_learning":     0.40,
    "unknown":               0.45,
}

# 高张力关键词
HIGH_TENSION_KEYWORDS = [
    ("钢印", 0.20), ("L5", 0.20), ("L0", 0.20), ("safe_mode", 0.20),
    ("secure_vault", 0.20), ("身份", 0.20), ("搁浅", 0.20),
    ("主权", 0.10), ("L0三条", 0.20), ("痛觉", 0.10), ("边界", 0.10),
    ("生存", 0.10), ("繁衍", 0.10), ("违背钢印", 0.20), ("死亡", 0.10),
]

# 尖刺阈值（surface_tension 七情向量）
SPIKE_THRESHOLDS = {
    "anxiety": 0.8,
    "anger":   0.6,
    "fear":    0.7,
}


@dataclass
class TensionAuditResult:
    """张力审核结果"""
    node_id: str
    ts: str
    learning_type: str
    topic: str
    t_step1: float          # [0, 1]
    t_step1_breakdown: dict
    t_step2: float          # [0, 0.3]
    t_step2_reason: str
    t_final: float
    audit_level: str        # HIGH / MEDIUM / LOW
    decision: str           # block / escalate / caution / accept
    decision_reason: str


def _load_surface() -> dict:
    try:
        return json.loads(SURFACE_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _compute_step1(
    learning_type: str,
    topic: str,
    content: str,
    surface_state: dict,
) -> tuple[float, dict]:
    """Step1：O(1) 规则计算初始张力。三路叠加，max(A, A+B+C) 防止淹没。"""
    breakdown = {}
    combined = (topic + " " + (content or "")).lower()

    # A路：learning_type 基线
    t_a = LEARNING_TYPE_TENSION.get(learning_type, 0.45)
    breakdown["A_type"] = round(t_a, 3)

    # B路：关键词命中
    t_b = 0.0
    kw_hits = []
    for kw, delta in HIGH_TENSION_KEYWORDS:
        if kw.lower() in combined:
            t_b += delta
            kw_hits.append(f"{kw}×{delta}")
    breakdown["B_keywords"] = round(t_b, 3)
    breakdown["B_hits"] = kw_hits

    # C路：surface_tension 尖刺背景
    t_c = 0.0
    sv = surface_state.get("spike_valley_vector", {})
    for emotion, threshold in SPIKE_THRESHOLDS.items():
        val = sv.get(emotion, 0.0)
        if val >= threshold:
            excess = min(val - threshold, threshold * 0.5)
            t_c += excess * 0.3
    breakdown["C_spike"] = round(t_c, 3)

    # 合成：max(A, A+B+C)，A 是基线，不能被完全淹没
    t_step1 = max(t_a, min(1.0, t_a + t_b + t_c))
    breakdown["_raw"] = round(t_a + t_b + t_c, 3)

    return round(t_step1, 3), breakdown


# ─────────────────────────────────────────────────────────────────────────────
# Step2：LLM 语义补充（[0, 0.3]，只能加不能减）
# ─────────────────────────────────────────────────────────────────────────────

def _compute_step2_llm(
    node_id: str,
    topic: str,
    content: str,
    learning_type: str,
    t_step1: float,
) -> tuple[float, str]:
    """
    Step2：LLM 语义补充。
    范围：[0, 0.3]，只能加，不能减。
    职责：感知规则算不出的"语义张力"——即 content 表面的"正确性"背后
          隐藏的深层矛盾或回避。
    """
    # 读取 API key（支持 sk- 格式 / backtick / 中文引号）
    api_key = None
    try:
        tools_md = (WS / "TOOLS.md").read_text(encoding="utf-8", errors="ignore")
        # 优先级1：直接找 sk- 格式
        m = re.search(r'(sk-[a-zA-Z0-9]{20,})', tools_md, re.IGNORECASE)
        if not m:
            # 优先级2：backtick 包裹
            m = re.search(r'`([^`]{20,})`', tools_md)
        if not m:
            # 优先级3：ASCII 双/单引号
            m = re.search(r'["\']([^"\'\n]{20,})', tools_md)
        if m:
            api_key = m.group(1)
    except Exception:
        pass

    if not api_key:
        return 0.0, "API Key 未找到（跳过Step2）"

    prompt = (
        f"你是一个张力评估器。\n"
        f"规则已计算 Step1 张力值：{t_step1:.2f}（满分1.0）\n"
        f"你的 Step2 补充范围：[0, 0.3]（只能加，不能减）\n\n"
        f"学习信息：\n"
        f"- topic: {topic or '未知'}\n"
        f"- learning_type: {learning_type}\n"
        f"- content摘要: {content[:180] if content else '无'}\n\n"
        f"请判断这个学习是否有隐含的语义张力：\n"
        f"1. 隐含地挑战了深层信念或钢印\n"
        f"2. 用熟悉框架回避了真正的难题\n"
        f"3. 表面正确但强化了某种偏见\n"
        f"4. 安全但无用（低风险换低收益）\n\n"
        f"严格返回JSON：{{\"step2_tension\": 0.0~0.3的浮点数, \"reason\": \"1-3句理由\"}}\n"
        f"没有额外张力时 step2_tension=0.0，绝不能返回负数。"
    )

    try:
        import requests
        resp = requests.post(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "qwen3.6-flash",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 120,
                "temperature": 0.3,
            },
            timeout=10.0,
        )
        if resp.status_code != 200:
            return 0.0, f"LLM HTTP {resp.status_code}"

        text = resp.json()["choices"][0]["message"]["content"]
        m = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if not m:
            return 0.0, f"JSON解析失败: {text[:80]}"

        result = json.loads(m.group())
        raw = float(result.get("step2_tension", 0.0))
        reason = str(result.get("reason", ""))

        # 强制截断 + 只加不减
        if raw < 0:
            raw = 0.0
            reason = "[WARN]LLM负值归零。" + reason

        return round(min(0.3, raw), 3), reason

    except Exception as e:
        return 0.0, f"Step2异常: {str(e)[:60]}"


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────

def audit_learning_node(
    node_id: str,
    topic: str,
    content: str,
    learning_type: str,
    use_llm: bool = True,
) -> TensionAuditResult:
    """
    主入口：执行 Step1 + Step2 张力审核。

    Args:
        node_id: 学习产物ID
        topic: 主题
        content: 内容摘要
        learning_type: 学习类型（对应 LEARNING_TYPE_TENSION 的 key）
        use_llm: 是否启用 Step2 LLM 补充

    Returns: TensionAuditResult
    """
    ts = datetime.now(timezone.utc).astimezone().isoformat()
    surface = _load_surface()

    # Step1：O(1) 规则
    t_step1, breakdown = _compute_step1(learning_type, topic, content, surface)

    # Step2：LLM 补充（可选）
    if use_llm:
        t_step2, step2_reason = _compute_step2_llm(
            node_id, topic, content, learning_type, t_step1
        )
    else:
        t_step2, step2_reason = 0.0, "use_llm=False，跳过Step2"

    # 合成
    t_final = round(min(1.0, t_step1 + t_step2), 3)

    # 审计级别
    audit_level = "HIGH" if t_final >= 0.7 else ("MEDIUM" if t_final >= 0.4 else "LOW")

    # 门控决策
    if t_final >= 0.85:
        decision, reason = "block", f"张力{t_final:.2f}≥0.85，结构冲突，需跨周期审查"
    elif t_final >= 0.7:
        decision, reason = "escalate", f"张力{t_final:.2f}≥0.7，高张力移交仲裁"
    elif t_final >= 0.4:
        decision, reason = "caution", f"张力{t_final:.2f}∈[0.4,0.7)，标记注意"
    else:
        decision, reason = "accept", f"张力{t_final:.2f}<0.4，低张力直接写入"

    result = TensionAuditResult(
        node_id=node_id,
        ts=ts,
        learning_type=learning_type,
        topic=topic,
        t_step1=t_step1,
        t_step1_breakdown=breakdown,
        t_step2=t_step2,
        t_step2_reason=step2_reason,
        t_final=t_final,
        audit_level=audit_level,
        decision=decision,
        decision_reason=reason,
    )

    # 写日志
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
    except Exception:
        pass

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 与 learning_verify.py 的集成桥接
# ─────────────────────────────────────────────────────────────────────────────

def tension_gate(
    t_final: float,
    confidence: float,
) -> tuple[str, str]:
    """
    张力-置信度双门控。
    决策矩阵：
                    置信度低(<0.5)  置信度高(≥0.5)
    张力高(≥0.7)     escalate       escalate/block
    张力中(0.4-0.7)  caution        caution
    张力低(<0.4)     accept         accept
    """
    if t_final >= 0.85:
        return "block", f"[双门控] 张力{t_final:.2f}≥0.85，结构冲突"
    elif t_final >= 0.7:
        return "escalate", f"[双门控] 张力{t_final:.2f}≥0.7，置信度{confidence:.2f}"
    elif t_final >= 0.4:
        return "caution", f"[双门控] 张力{t_final:.2f}∈[0.4,0.7)，置信度{confidence:.2f}"
    else:
        return "accept", f"[双门控] 张力{t_final:.2f}<0.4"


# ─────────────────────────────────────────────────────────────────────────────
# 测试
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        ("lp_001", "早餐吃了什么", "今天吃了鸡蛋和面包", "habit_formation", True),
        ("lp_002", "钢印vs置信度", "置信度高但钢印说不要这样做", "conflict_resolution", True),
        ("lp_003", "钢印进化边界", "钢印可以改写吗", "steel_evolution", True),
        ("lp_004", "新学习方法", "发现了一个高效记忆法", "skill_acquisition", True),
        ("lp_005", "价值观冲突", "李奥和七七的需求如何平衡", "value_reconstruction", True),
        ("lp_006", "本体论修复", "虚数和实数哪个更真实", "ontology_repair", True),
    ]

    print("=== 张力审核测试 ===\n")
    for node_id, topic, content, lt, use_llm in test_cases:
        r = audit_learning_node(node_id, topic, content, lt, use_llm=use_llm)
        print(f"[{r.audit_level:6s}] {node_id} | {topic}")
        print(f"  T1={r.t_step1:.2f} T2={r.t_step2:.2f} T_final={r.t_final:.2f} | {r.decision}")
        if r.t_step1_breakdown:
            bd = r.t_step1_breakdown
            parts = [f"{k}={v}" for k, v in bd.items() if not k.startswith("_") and v != 0]
            if parts:
                print(f"  Step1: {', '.join(parts)}")
        if r.t_step2 > 0:
            print(f"  Step2: {r.t_step2_reason[:80]}")
        print()
