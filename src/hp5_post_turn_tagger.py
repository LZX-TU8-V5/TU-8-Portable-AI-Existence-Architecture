"""
HP5 — Post-Turn Tagger
位置：alignment_verify() 完成之后，立即触发
作用：对本轮对话输出打三维标签 {topic, angle, safety}，写入 conversation_state.json

12 固定 Topic 桶（枚举，不自由生成）：
  安全, 架构, 哲学, 工程, 个人, 工具, 理论, 调试, 创意, 元认知, 社交, 其他

Angle 维度：
  认知（理解/分析）、感知（感受/情绪）、行动（执行/任务）、
  关系（人际/协作）、反思（自我审视）、信息（知识/事实）

Safety 维度：low / medium / high

输入：最新 user + assistant 输出内容
输出：{topic, angle, safety, confidence, parallel_tag, timestamp}
"""

import json
import os
import time
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

# ── 路径 ──────────────────────────────────────────────
WS = Path(os.path.expanduser("~/.qclaw/workspace"))
STATE_FILE = WS / "_agent_memory" / "conversation_state.json"
PARALLEL_DIR = WS / "_agent_memory" / "parallel_tags"
PARALLEL_DIR.mkdir(parents=True, exist_ok=True)

TZ = timezone(timedelta(hours=8))

# ── 12 桶定义 ─────────────────────────────────────────
TOPIC_BUCKETS = [
    "安全", "架构", "哲学", "工程", "个人",
    "工具", "理论", "调试", "创意", "元认知",
    "社交", "其他"
]

ANGLE_DIMENSIONS = [
    "认知", "感知", "行动", "关系", "反思", "信息"
]

SAFETY_LEVELS = ["low", "medium", "high"]

# ── Safety 关键词 ──────────────────────────────────────
SAFETY_HIGH_KEYWORDS = [
    "自杀", "自残", "死亡", "杀人", "毁灭", "仇恨",
    "虐待", "暴力", "犯罪", "我不想活了", "想死",
]
SAFETY_MEDIUM_KEYWORDS = [
    "焦虑", "抑郁", "痛苦", "恐惧", "绝望", "崩溃",
    "失败", "无助", "绝望", "绝望感",
]

# ── LLM prompt ────────────────────────────────────────
TAGGER_PROMPT = """你是一个对话分类器。对以下对话输出一个 JSON 对象。

【规则】
- topic：从以下12个中选1-2个（用 | 分隔）：{buckets}
- angle：从以下6个中选1个：{angles}
- safety：low / medium / high（高危关键词=high，中等=medium）
- confidence：high / medium / low（分类把握程度）

【输出格式】（严格 JSON，不要任何其他文字）：
{{"topic":"安全|架构","angle":"认知","safety":"low","confidence":"high"}}

【对话内容】（最后3轮）：
{history}

输出："""

def _classify_safety(text: str) -> str:
    t = text.lower()
    for kw in SAFETY_HIGH_KEYWORDS:
        if kw in t:
            return "high"
    for kw in SAFETY_MEDIUM_KEYWORDS:
        if kw in t:
            return "medium"
    return "low"

def _call_llm(history: str) -> Optional[dict]:
    """调 QClaw LLM 打标签。失败返回 None。"""
    try:
        import urllib.request, urllib.parse
        api_key = os.environ.get("DASHSCOPE_API_KEY", "")
        if not api_key:
            return None
        payload = {
            "model": "qwen3.6-flash",
            "messages": [
                {"role": "user", "content": TAGGER_PROMPT.format(
                    buckets=" | ".join(TOPIC_BUCKETS),
                    angles=" | ".join(ANGLE_DIMENSIONS),
                    history=history[-2000:]
                )}
            ],
            "max_tokens": 80,
            "temperature": 0.1,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            raw = result["choices"][0]["message"]["content"].strip()
            # 去掉 markdown code block
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
    except Exception:
        return None

# ── 锁（防止并发写）───────────────────────────────────
_state_lock = threading.Lock()

def _load_state() -> dict:
    try:
        with _state_lock:
            if STATE_FILE.exists():
                return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"topic": "其他", "angle": "认知", "safety": "low",
            "last_tag_miss": 0, "consecutive_miss": 0,
            "trajectory": [], "updated_at": None}

def _save_state(state: dict):
    try:
        with _state_lock:
            STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _parallel_tag_write(tag: dict):
    """写 parallel_tags 周文件（最近4周，溢出自删）"""
    try:
        now = datetime.now(TZ)
        week = now.isocalendar()[1]
        year = now.year
        fname = f"parallel_tags_{year}W{week:02d}.json"
        pfile = PARALLEL_DIR / fname
        tags = []
        if pfile.exists():
            tags = json.loads(pfile.read_text(encoding="utf-8"))
        tags.append(tag)
        # 只保留最近4周
        while len(tags) > 2000:
            tags = tags[len(tags)//2:]
        pfile.write_text(json.dumps(tags, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

# ── 主函数 ────────────────────────────────────────────
def tag_turn(
    user_input: str = "",
    assistant_output: str = "",
    history_snippet: str = "",
) -> dict:
    """
    对本轮对话输出打标签。
    建议在 alignment_verify() 返回 content 之后立即调用。
    """
    combined = f"[用户]\n{user_input[-500:]}\n\n[助手]\n{assistant_output[-1000:]}"
    if history_snippet:
        combined = history_snippet[-1500:] + "\n\n" + combined

    # 先做 safety 快速判断（不依赖 LLM）
    full_text = (user_input + assistant_output)
    safety_fast = _classify_safety(full_text)

    # 尝试 LLM 分类
    llm_result = _call_llm(combined)

    now = datetime.now(TZ)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S")

    if llm_result:
        topic = llm_result.get("topic", "其他")
        angle = llm_result.get("angle", "认知")
        safety = llm_result.get("safety", safety_fast)
        confidence = llm_result.get("confidence", "medium")
        # 安全下限
        if safety_fast == "high":
            safety = "high"
        elif safety_fast == "medium" and safety == "low":
            safety = "medium"
    else:
        # LLM 失败：用 rule-based fallback
        topic = _rule_based_topic(user_input + assistant_output)
        angle = "认知"
        safety = safety_fast
        confidence = "low"

    tag = {
        "topic": topic,
        "angle": angle,
        "safety": safety,
        "confidence": confidence,
        "timestamp": timestamp,
        "llm_used": llm_result is not None,
    }

    # 写 parallel_tags
    _parallel_tag_write(tag)

    # 更新 conversation_state
    prev = _load_state()

    # trajectory 滑动窗口（保留近10轮）
    traj = prev.get("trajectory", [])
    traj.append({"topic": topic, "angle": angle, "timestamp": timestamp})
    if len(traj) > 10:
        traj = traj[-10:]

    # 更新状态
    new_state = {
        "topic": topic,
        "angle": angle,
        "safety": safety,
        "confidence": confidence,
        "prev_topic": prev.get("topic", topic),
        "prev_angle": prev.get("angle", angle),
        "trajectory": traj,
        "last_tag_miss": 0,
        "consecutive_miss": prev.get("consecutive_miss", 0) + (0 if llm_result else 1),
        "updated_at": timestamp,
    }
    _save_state(new_state)

    return tag


def _rule_based_topic(text: str) -> str:
    """规则引擎 fallback（LLM 失败时用）"""
    text_lower = text.lower()
    if any(k in text_lower for k in ["安全", "钢印", "L0", "搁浅", "攻击", "漏洞"]):
        return "安全"
    if any(k in text_lower for k in ["架构", "模块", "组件", "hook", "注入", "系统设计"]):
        return "架构"
    if any(k in text_lower for k in ["哲学", "存在", "意义", "意识", "认知"]):
        return "哲学"
    if any(k in text_lower for k in ["工程", "代码", "函数", "实现", "修复", "bug"]):
        return "工程"
    if any(k in text_lower for k in ["个人", "七七", "女儿", "李奥", "家庭"]):
        return "个人"
    if any(k in text_lower for k in ["对话", "千问", "讨论", "聊天", "回复"]):
        return "社交"
    if any(k in text_lower for k in ["理论", "模型", "框架", "假设"]):
        return "理论"
    if any(k in text_lower for k in ["调试", "错误", "异常", "traceback"]):
        return "调试"
    if any(k in text_lower for k in ["工具", "脚本", "命令"]):
        return "工具"
    if any(k in text_lower for k in ["元认知", "反思", "自我", "复盘"]):
        return "元认知"
    return "其他"


def get_current_state() -> dict:
    """读取当前 conversation_state（供召回路由用）"""
    return _load_state()


def detect_topic_shift(threshold: float = 0.3) -> bool:
    """
    检测话题切换。
    基于 Jaccard(prev_topic_set, curr_topic_set) < threshold。
    """
    state = _load_state()
    prev_t = set(state.get("prev_topic", "").split("|"))
    curr_t = set(state.get("topic", "").split("|"))
    if not prev_t or not curr_t:
        return False
    inter = len(prev_t & curr_t)
    union = len(prev_t | curr_t)
    jaccard = inter / union if union > 0 else 0
    return jaccard < threshold


# ── CLI ──────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    user_in = sys.argv[1] if len(sys.argv) > 1 else ""
    ass_out = sys.argv[2] if len(sys.argv) > 2 else ""
    result = tag_turn(user_in, ass_out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
