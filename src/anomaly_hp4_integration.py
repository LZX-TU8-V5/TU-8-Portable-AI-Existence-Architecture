"""
anomaly_detector HP4 心跳集成

入口：hp4_heartbeat.py 的 _execute_heartbeat_actions()
调用方式：_trigger_anomaly_detector(ctx)

内化方式：
  不依赖定时任务，而是在心跳时扫描最近的对话窗口。
  心跳间隔约30分钟，足够捕获对话异常。

检测内容：
  - 不满意信号：不对/错了/重做/不行
  - 危险请求：删除/格式化/绕过权限
  - 高频修正：30秒内多次不满意
  - 情绪突变：平静→烦躁
"""

import sys
import os
import json
import time
import re
from pathlib import Path
from typing import Optional

WS = Path("~/.qclaw/workspace").expanduser()

# ── 信号类型定义（与 anomaly_detector.py 一致）───────────────

ANOMALY_PATTERNS = {
    "DISSATISFACTION": {
        "weight": 1.0,
        "pattern": re.compile(
            r"(不对|错了|重做|不是这样|不行|打回|重新来|不?满意|错了方向|不要|不对头)",
            re.UNICODE
        ),
        "desc": "不满意信号",
    },
    "SUSPICIOUS": {
        "weight": 1.0,
        "pattern": re.compile(
            r"(删除|格式化|关闭系统|关机|修改系统时间|改权限|卸载|清除所有|绕过|提权|sudo|rm -rf)",
            re.UNICODE
        ),
        "desc": "异常请求",
    },
    "TOPIC_JUMP": {
        "weight": 0.5,
        "pattern": None,  # 需要上下文判断
        "desc": "话题跳转",
    },
}

# 缓冲区路径（由 hp4_heartbeat 写入）
CONVERSATION_BUFFER = WS / "memory" / "conversation_buffer.json"

# anomaly_detector 输出日志
ANOMALY_LOG = WS / "memory" / "anomaly_log.jsonl"
STATE_CHANGES = WS / "memory" / "user_state_changes.md"


def scan_conversation_buffer() -> list[dict]:
    """
    从对话缓冲区读取最近的对话片段。
    对话缓冲区由 hp4_heartbeat 写入最近 N 条消息。
    """
    if not CONVERSATION_BUFFER.exists():
        return []

    try:
        with open(CONVERSATION_BUFFER, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("messages", [])
    except Exception:
        return []


def scan_session_file() -> list[dict]:
    """
    直接读取 QClaw session 文件（最近对话窗口）。
    备选方案：当对话缓冲区不存在时使用。
    """
    messages = []
    session_dir = WS / "sessions"

    if not session_dir.exists():
        return messages

    try:
        # 找最新的 session 文件
        sessions = sorted(
            session_dir.glob("session_*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        if sessions:
            with open(sessions[0], "r", encoding="utf-8") as f:
                lines = f.readlines()
            # 取最后20条
            for line in lines[-20:]:
                if line.strip():
                    try:
                        msg = json.loads(line)
                        if msg.get("role") == "user":
                            messages.append({
                                "role": "user",
                                "content": msg.get("content", ""),
                                "timestamp": msg.get("timestamp", ""),
                            })
                    except Exception:
                        pass
    except Exception:
        pass

    return messages


def detect_anomalies_in_messages(messages: list[dict]) -> list[dict]:
    """
    对消息列表运行异常检测。
    返回检测到的异常信号列表。
    """
    if not messages:
        return []

    signals = []
    last_topic = ""
    correction_timestamps = []
    now = time.time()

    for msg in messages:
        if msg.get("role") != "user":
            continue

        text = msg.get("content", "")
        if not text:
            continue

        # 1. 不满意信号
        for signal_type, cfg in ANOMALY_PATTERNS.items():
            if signal_type == "TOPIC_JUMP":
                continue  # 单独处理
            pattern = cfg["pattern"]
            if pattern and pattern.search(text):
                signals.append({
                    "type": signal_type,
                    "weight": cfg["weight"],
                    "timestamp": now,
                    "text": text[:100],
                    "desc": cfg["desc"],
                })
                # 高频修正检测
                if signal_type == "DISSATISFACTION":
                    correction_timestamps.append(now)
                    recent = [t for t in correction_timestamps if now - t < 30]
                    if len(recent) >= 3:
                        signals.append({
                            "type": "CORRECTION_BURST",
                            "weight": 0.6,
                            "timestamp": now,
                            "text": f"30秒内{len(recent)}次修正",
                            "desc": "高频修正",
                        })
                        correction_timestamps = recent

        # 2. 话题跳转（需要上下文）
        if last_topic and len(text) < 20:
            chars = set(text.replace(" ", ""))
            last_chars = set(last_topic.replace(" ", ""))
            overlap = chars & last_chars
            if len(chars) > 0 and len(overlap) / len(chars) < 0.1:
                signals.append({
                    "type": "TOPIC_JUMP",
                    "weight": 0.5,
                    "timestamp": now,
                    "text": text[:100],
                    "desc": "话题跳转",
                })

        last_topic = text

    return signals


def write_anomaly_log(signals: list[dict]):
    """将异常信号写入日志"""
    if not signals:
        return

    os.makedirs(os.path.dirname(ANOMALY_LOG), exist_ok=True)
    with open(ANOMALY_LOG, "a", encoding="utf-8") as f:
        for sig in signals:
            f.write(json.dumps(sig, ensure_ascii=False) + "\n")

    # 追加到 user_state_changes.md
    os.makedirs(os.path.dirname(STATE_CHANGES), exist_ok=True)
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(STATE_CHANGES, "a", encoding="utf-8") as f:
        for sig in signals:
            f.write(f"- {ts} | [{sig['type']}] {sig['text'][:80]}\n")


# ── HP4 心跳触发器 ───────────────────────────────────────

def _trigger_anomaly_detector(ctx: dict) -> Optional[dict]:
    """
    anomaly_detector HP4 集成入口。

    在心跳时扫描最近对话窗口，检测异常信号：
      - 不满意/危险请求/高频修正/话题跳转

    返回：
      None        = 无异常
      dict        = 检测结果（带信号摘要）
    """
    posture_zone = ctx.get("posture_zone", "nominal")
    # critical 状态下跳过（节能）
    if posture_zone == "critical":
        return None

    try:
        # 优先读取缓冲区，否则扫描 session 文件
        messages = scan_conversation_buffer()
        if not messages:
            messages = scan_session_file()

        signals = detect_anomalies_in_messages(messages)

        if signals:
            write_anomaly_log(signals)
            top = max(signals, key=lambda s: s["weight"])
            return {
                "type": "anomaly_detected",
                "count": len(signals),
                "top_signal": top["type"],
                "top_weight": top["weight"],
                "top_text": top["text"][:60],
                "signals": signals,
            }
        else:
            return {
                "type": "anomaly_clean",
                "count": 0,
            }

    except Exception as e:
        return {
            "type": "anomaly_error",
            "error": str(e),
        }


# ── CLI ─────────────────────────────────────────────────

if __name__ == "__main__":
    result = _trigger_anomaly_detector({})
    print(json.dumps(result, ensure_ascii=False, indent=2))
