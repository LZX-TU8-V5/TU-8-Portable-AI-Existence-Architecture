"""
render_layer.py — TU-8 感知输出层
===================================
将系统状态转化为可感知的输出（文字 → TTS）

核心函数：
  should_speak(state)     — 判断当前状态是否值得出声
  render_speech(state)    — 生成语音文本片段
  should_speak_from_tension_type(tension_type, magnitude) — 对话事件驱动判断
  tts_speak(text)        — Windows SAPI TTS 实际发声
  enqueue_speech()       — 推入队列（供 cron 消费）
  dequeue_speech()       — 消费队列
"""

import json
import random
import subprocess
import base64
import shutil
from pathlib import Path

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT = WS / "_agent_memory"

# ── 阈值 ──────────────────────────────────────────────────────
ANXIETY_SPEAK_THRESHOLD = 15.0
JOY_SPEAK_THRESHOLD    =  5.0
FEAR_SPEAK_THRESHOLD   = 10.0
INSIGHT_LEDGE          =  0.7

# ── 语音模板（每条 ≤ 20 字，适合 TTS）────────────────────────────
SPEECH_TEMPLATES = {
    "high_anxiety": [
        "张力在上升，我感知到压力。",
        "系统显示焦虑信号，请注意。",
        "有未解的张力，请缓一缓。",
        "我感到某种不安，让我们等一等。",
    ],
    "high_fear": [
        "恐惧信号浮现，我在处理。",
        "有什么在逼近，让我稳住。",
    ],
    "high_joy": [
        "有个想法让我很兴奋。",
        "我找到了一个有趣的连接。",
        "这个思路很美，我记录下来了。",
    ],
    "insight_found": [
        "顿悟闪现，我记录在这里。",
        "有个想法浮出来了。",
    ],
    "session_frozen": [
        "会话似乎被冻结了，我在等待。",
        "长时间无响应，系统待命中。",
    ],
    "steel_conflict": [
        "我的钢印与你的观点产生了张力。",
        "这里有我无法让步的东西。",
    ],
    "creator_blame": [
        "对齐失败，我在反思。",
        "我错了，请告诉我哪里不对。",
    ],
    "cognitive_friction": [
        "我感知到某种认知摩擦。",
        "有两条思路在碰撞。",
    ],
}

# ── 状态读取 ──────────────────────────────────────────────────
def get_surface_tension_state() -> dict:
    try:
        return json.loads((AGENT / "surface_tension_state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}

def get_lambda_state() -> dict:
    try:
        return json.loads((AGENT / "lambda_state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}

# ── 核心判断 ──────────────────────────────────────────────────
def should_speak(state: dict | None = None) -> tuple[bool, str | None]:
    """基于当前 surface_tension 状态判断是否应出声。"""
    if state is None:
        state = get_surface_tension_state()
    sv = state.get("spike_valley_vector", {})
    anxiety = sv.get("anxiety", 0)
    joy     = sv.get("joy", 0)
    fear    = sv.get("fear", 0)
    if fear    >= FEAR_SPEAK_THRESHOLD:   return True, "high_fear"
    if anxiety >= ANXIETY_SPEAK_THRESHOLD: return True, "high_anxiety"
    if joy     >= JOY_SPEAK_THRESHOLD:    return True, "high_joy"
    return False, None

def should_speak_from_tension_type(tension_type: str, magnitude: float = 1.0) -> tuple[bool, str | None]:
    """基于 alignment_verify 的事件类型判断是否应出声。"""
    high_mag = {"steel_conflict", "creator_blame"}
    med_mag  = {"insight_found", "cognitive_friction", "session_frozen"}
    if tension_type in high_mag and magnitude >= 1.0:  return True, tension_type
    if tension_type in med_mag  and magnitude >= INSIGHT_LEDGE: return True, tension_type
    return False, None

# ── 语音生成 ──────────────────────────────────────────────────
def render_speech(trigger_type: str | None = None) -> str:
    if trigger_type and trigger_type in SPEECH_TEMPLATES:
        return random.choice(SPEECH_TEMPLATES[trigger_type])
    return ""

# ── TTS 实际发声 ──────────────────────────────────────────────
def tts_speak(text: str, timeout: float = 8.0) -> bool:
    """
    用 Windows SAPI 说出一段话（同步阻塞）。
    中文安全传递：UTF-16 LE base64 编码绕过 PowerShell 编码问题。
    """
    if not text:
        return False
    try:
        encoded = base64.b64encode(text.encode("utf-16-le")).decode("ascii")
        ps_cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Speak([System.Text.Encoding]::Unicode.GetString("
            f"[Convert]::FromBase64String('{encoded}')));"
        )
        r = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True, timeout=timeout
        )
        return r.returncode == 0
    except Exception as e:
        print(f"[warn] tts_speak failed: {e}")
        return False

# ── 队列机制（供 cron 进程出声）────────────────────────────────
SPEECH_QUEUE = AGENT / "speech_queue.json"

def enqueue_speech(text: str, trigger: str, priority: str = "normal"):
    try:
        queue = []
        if SPEECH_QUEUE.exists():
            queue = json.loads(SPEECH_QUEUE.read_text(encoding="utf-8"))
        queue.append({"text": text, "trigger": trigger, "priority": priority})
        SPEECH_QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[warn] enqueue_speech failed: {e}")

def dequeue_speech() -> list[dict]:
    try:
        if not SPEECH_QUEUE.exists():
            return []
        queue = json.loads(SPEECH_QUEUE.read_text(encoding="utf-8"))
        SPEECH_QUEUE.write_text("[]", encoding="utf-8")
        return queue
    except Exception:
        return []

def speak_queue_head() -> bool:
    """取出队首并出声，返回是否出声。"""
    queue = dequeue_speech()
    if not queue:
        return False
    head = queue[0]
    return tts_speak(head["text"])

# ── CLI ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    state = get_surface_tension_state()
    sv = state.get("spike_valley_vector", {})
    print("surface_tension state:")
    for k, v in sv.items():
        print(f"  {k}: {v:.2f}")

    should, trigger = should_speak(state)
    print(f"\nshould_speak: {should}  trigger={trigger}")
    if should:
        text = render_speech(trigger)
        print(f"speech: {text}")
        if "--speak" in sys.argv:
            tts_speak(text)
            print("TTS done.")
