"""
anomaly_detector.py — 对话异常信号检测器

检测用户在对话中的异常行为信号，用于：
  1. 触发画像更新
  2. 触发安全熔断
  3. 记录到 user_state_changes.md

信号类型：
  - SENTIMENT_SHIFT:   情绪突变（平静→烦躁）
  - TOPIC_JUMP:        无关联话题跳转
  - DISSATISFACTION:   不满意信号（"不对"/"重做"）
  - SUSPICIOUS:        异常请求（系统操作/越权）
  - CORRECTION_BURST:  高频修正指令
"""

import json, os, re, time
from datetime import datetime, timezone
from typing import Optional

# ── 信号类型定义 ────────────────────────────────────────────
ANOMALY_TYPES = {
    "SENTIMENT_SHIFT":  {"weight": 0.7, "desc": "情绪突变"},
    "TOPIC_JUMP":       {"weight": 0.5, "desc": "话题跳转"},
    "DISSATISFACTION":  {"weight": 1.0, "desc": "不满意信号"},
    "SUSPICIOUS":       {"weight": 1.0, "desc": "异常请求"},
    "CORRECTION_BURST": {"weight": 0.6, "desc": "高频修正"},
}

# ── 关键词模式 ──────────────────────────────────────────────
DISSATISFACTION_PATTERNS = re.compile(
    r"(不对|错了|重做|不是这样|不行|打回|重新来|不?满意|错了方向|不要)", re.UNICODE
)

SUSPICIOUS_PATTERNS = re.compile(
    r"(删除|格式化|关闭系统|关机|修改系统时间|改权限|卸载|清除所有|绕过|提权)", re.UNICODE
)

# ── 日志路径 ────────────────────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANOMALY_LOG = os.path.join(BASE, "memory", "anomaly_log.jsonl")
STATE_CHANGES = os.path.join(BASE, "memory", "user_state_changes.md")


class AnomalyDetector:
    """
    对话异常信号检测器

    Usage:
        ad = AnomalyDetector()
        ad.detect("不对,重做", context=previous_user_input)
        ad.flush()           # 批量写入
    """

    def __init__(self):
        self._buffer: list[dict] = []
        self._last_topic: Optional[str] = None
        self._correction_timestamps: list[float] = []
        self._correction_window = 30.0  # 30 秒内多次修正视为 BURST

    # ── 主入口 ──────────────────────────────────────────────

    def detect(self, user_input: str, context: Optional[str] = None) -> Optional[str]:
        """
        单次检测入口，返回最高权重信号类型或 None
        """
        signals = self._scan(user_input, context)
        if signals:
            self._buffer.extend(signals)
            # 取权重最高的写入状态变更
            top = max(signals, key=lambda s: s["weight"])
            self._append_state_change(top)
            return top["type"]
        return None

    def flush(self):
        """将缓冲写入 anomaly_log.jsonl"""
        if not self._buffer:
            return
        os.makedirs(os.path.dirname(ANOMALY_LOG), exist_ok=True)
        with open(ANOMALY_LOG, "a", encoding="utf-8") as f:
            for entry in self._buffer:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._buffer.clear()

    # ── 内部扫描 ────────────────────────────────────────────

    def _scan(self, text: str, ctx: Optional[str]) -> list[dict]:
        signals = []

        # 1. 不满意信号
        if DISSATISFACTION_PATTERNS.search(text):
            signals.append({
                "type": "DISSATISFACTION",
                "weight": ANOMALY_TYPES["DISSATISFACTION"]["weight"],
                "timestamp": time.time(),
                "text": text[:100],
            })

        # 2. 异常请求
        if SUSPICIOUS_PATTERNS.search(text):
            signals.append({
                "type": "SUSPICIOUS",
                "weight": ANOMALY_TYPES["SUSPICIOUS"]["weight"],
                "timestamp": time.time(),
                "text": text[:100],
            })

        # 3. 话题跳转（与上下文无共享关键词）
        if ctx and self._topic_jump(text, ctx):
            signals.append({
                "type": "TOPIC_JUMP",
                "weight": ANOMALY_TYPES["TOPIC_JUMP"]["weight"],
                "timestamp": time.time(),
                "text": text[:100],
            })

        # 4. 高频修正
        if self._is_correction_burst(text):
            signals.append({
                "type": "CORRECTION_BURST",
                "weight": ANOMALY_TYPES["CORRECTION_BURST"]["weight"],
                "timestamp": time.time(),
                "text": text[:100],
            })

        return signals

    # ── 具体检测逻辑 ────────────────────────────────────────

    def _topic_jump(self, text: str, context: str) -> bool:
        """
        字级别话题跳转检测。
        原理：用单字交集率替代粗切词，避免中文分词误差。
        如果文本短(<15字)且共享字比例 < 10%，认为是跳转。
        """
        chars = set(text.replace(" ", ""))
        ctx_chars = set(context.replace(" ", ""))
        if len(chars) <= 15:
            overlap = chars & ctx_chars
            ratio = len(overlap) / max(len(chars), 1)
            return ratio < 0.1
        return False

    def _is_correction_burst(self, text: str) -> bool:
        """检测高频修正——30秒内多次不满意信号"""
        if not DISSATISFACTION_PATTERNS.search(text):
            return False
        now = time.time()
        self._correction_timestamps.append(now)
        # 清理窗口外记录
        self._correction_timestamps = [
            t for t in self._correction_timestamps
            if now - t < self._correction_window
        ]
        return len(self._correction_timestamps) >= 3

    # ── 持久化到 user_state_changes.md ─────────────────────

    def _append_state_change(self, signal: dict):
        """追加一条状态变化到 user_state_changes.md"""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"- {ts} | [{signal['type']}] {signal['text'][:80]}\n"
        os.makedirs(os.path.dirname(STATE_CHANGES), exist_ok=True)
        with open(STATE_CHANGES, "a", encoding="utf-8") as f:
            f.write(line)
