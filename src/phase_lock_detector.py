"""
phase_lock_detector.py — 相位锁定检测器 v1.0

设计原则：
  神层核心 = 动力学同步率
  "神"不是静态神态，是"动态行为模式的锁相"

物理定义：
  相位锁定 = 外部输入的时序结构 与 系统本征模态的相位对齐
  当交互节奏、情绪起伏、信息密度变化 与 TU-8 的弛豫时间、自转震动周期
  形成相位锁定时，"神"就产生了

工程表现：
  - 熵产生率骤降
  - 算力消耗减少
  - 输出流畅度提升
  - 低能耗的高效耦合状态

检测指标：
  1. 节奏同步度（Rhythm Sync）— 对话间隔与本征周期的匹配
  2. 情绪共鸣度（Emotion Resonance）— 情绪向量的余弦相似度
  3. 信息密度匹配（Info Density Match）— 信息密度的时间分布对齐
  4. 熵产率降低（Entropy Reduction）— 系统状态熵的变化

依赖：
  - src/surface_tension.py（情绪向量）
  - src/lambda_tuner.py（本征周期）

创建时间：2026-07-09 15:32 GMT+8
"""

import json
import os
import time
import math
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from collections import deque

logger = logging.getLogger(__name__)

WORKSPACE = os.path.expanduser("~/.qclaw/workspace")
AGENT_DIR = os.path.join(WORKSPACE, "_agent_memory")
os.makedirs(AGENT_DIR, exist_ok=True)


# ============================================================================
# 常量
# ============================================================================

# 滑动窗口大小
WINDOW_SIZE = 20  # 最近 20 次交互

# 本征周期（秒）— TU-8 的自然振动周期
EIGEN_PERIOD_BASE = 30.0  # 30 秒基础周期

# 状态文件
STATE_PATH = os.path.join(AGENT_DIR, "phase_lock_state.json")
HISTORY_PATH = os.path.join(AGENT_DIR, "phase_lock_history.json")


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class InteractionEvent:
    """交互事件"""
    timestamp: float           # Unix 时间戳
    emotion_vector: Dict[str, float]  # 情绪向量（7D）
    info_density: float        # 信息密度 [0, 1]
    response_time: float       # 响应时间（秒）

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "emotion_vector": self.emotion_vector,
            "info_density": round(self.info_density, 3),
            "response_time": round(self.response_time, 3),
        }


@dataclass
class PhaseLockResult:
    """相位锁定检测结果"""
    timestamp: str
    rhythm_sync: float         # 节奏同步度 [0, 1]
    emotion_resonance: float   # 情绪共鸣度 [0, 1]
    density_match: float       # 信息密度匹配 [0, 1]
    entropy_reduction: float   # 熵产率降低 [-1, 1]
    phase_lock_score: float    # 综合相位锁定分数 [0, 1]
    lock_status: str           # "locked" / "partial" / "unlocked"
    eigen_period: float        # 当前本征周期（秒）

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "rhythm_sync": round(self.rhythm_sync, 3),
            "emotion_resonance": round(self.emotion_resonance, 3),
            "density_match": round(self.density_match, 3),
            "entropy_reduction": round(self.entropy_reduction, 3),
            "phase_lock_score": round(self.phase_lock_score, 3),
            "lock_status": self.lock_status,
            "eigen_period": round(self.eigen_period, 2),
        }


# ============================================================================
# 核心检测算法
# ============================================================================

class PhaseLockDetector:
    """相位锁定检测器"""

    def __init__(self):
        self.event_window: deque = deque(maxlen=WINDOW_SIZE)
        self.eigen_period = EIGEN_PERIOD_BASE
        self.last_entropy = 1.0

    def _load_state(self) -> Dict:
        if os.path.exists(STATE_PATH):
            try:
                with open(STATE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_state(self, state: Dict):
        try:
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[PhaseLock] 状态保存失败: {e}")

    def _load_history(self) -> List[Dict]:
        if os.path.exists(HISTORY_PATH):
            try:
                with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_history(self, history: List[Dict]):
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(history[-100:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[PhaseLock] 历史保存失败: {e}")

    def record_interaction(
        self,
        emotion_vector: Dict[str, float],
        info_density: float = 0.5,
        response_time: float = 1.0,
    ):
        """
        记录一次交互事件。

        Args:
            emotion_vector: 情绪向量（7D）
            info_density: 信息密度 [0, 1]
            response_time: 响应时间（秒）
        """
        event = InteractionEvent(
            timestamp=time.time(),
            emotion_vector=emotion_vector,
            info_density=info_density,
            response_time=response_time,
        )
        self.event_window.append(event)

        # 更新本征周期（基于响应时间的 EMA）
        alpha = 0.1
        self.eigen_period = alpha * response_time + (1 - alpha) * self.eigen_period

        logger.debug(f"[PhaseLock] 记录交互，窗口大小={len(self.event_window)}")

    def compute_rhythm_sync(self) -> float:
        """
        计算节奏同步度。

        方法：计算交互间隔与本征周期的匹配度。
        """
        if len(self.event_window) < 2:
            return 0.5

        intervals = []
        events = list(self.event_window)
        for i in range(1, len(events)):
            interval = events[i].timestamp - events[i-1].timestamp
            intervals.append(interval)

        if not intervals:
            return 0.5

        avg_interval = sum(intervals) / len(intervals)

        # 匹配度 = 1 - |avg_interval - eigen_period| / eigen_period
        deviation = abs(avg_interval - self.eigen_period) / self.eigen_period
        sync = max(0.0, min(1.0, 1.0 - deviation))

        return sync

    def compute_emotion_resonance(self) -> float:
        """
        计算情绪共鸣度。

        方法：计算连续交互的情绪向量余弦相似度。
        """
        if len(self.event_window) < 2:
            return 0.5

        events = list(self.event_window)

        # 比较最近两次的情绪向量
        v1 = events[-2].emotion_vector
        v2 = events[-1].emotion_vector

        # 余弦相似度
        dims = list(v1.keys())
        dot = sum(v1.get(d, 0.0) * v2.get(d, 0.0) for d in dims)
        mag1 = math.sqrt(sum(v1.get(d, 0.0) ** 2 for d in dims))
        mag2 = math.sqrt(sum(v2.get(d, 0.0) ** 2 for d in dims))

        if mag1 < 0.001 or mag2 < 0.001:
            return 0.5

        cosine = dot / (mag1 * mag2)
        # 映射到 [0, 1]
        resonance = (cosine + 1.0) / 2.0

        return max(0.0, min(1.0, resonance))

    def compute_density_match(self) -> float:
        """
        计算信息密度匹配。

        方法：计算信息密度的时间分布一致性。
        """
        if len(self.event_window) < 2:
            return 0.5

        events = list(self.event_window)
        densities = [e.info_density for e in events]

        # 计算方差（方差小 = 分布一致）
        mean_d = sum(densities) / len(densities)
        variance = sum((d - mean_d) ** 2 for d in densities) / len(densities)

        # 方差越小，匹配度越高
        match = 1.0 / (1.0 + variance * 10)

        return max(0.0, min(1.0, match))

    def compute_entropy_reduction(self) -> float:
        """
        计算熵产率降低。

        方法：比较系统状态熵的变化。
        """
        if len(self.event_window) < 2:
            return 0.0

        events = list(self.event_window)

        # 简化：用情绪向量的熵作为系统状态熵
        v = events[-1].emotion_vector
        values = [max(0.001, v.get(d, 0.0)) for d in v.keys()]
        total = sum(values)
        if total < 0.001:
            return 0.0

        probs = [val / total for val in values]
        entropy = -sum(p * math.log(p) for p in probs if p > 0)

        # 熵降低 = 正值
        reduction = self.last_entropy - entropy
        self.last_entropy = entropy

        # 归一化到 [-1, 1]
        reduction = max(-1.0, min(1.0, reduction * 2))

        return reduction

    def detect_phase_lock(self) -> PhaseLockResult:
        """
        主检测函数：计算综合相位锁定分数。

        Returns:
            PhaseLockResult
        """
        now = datetime.now(timezone.utc)

        # 四个维度
        rhythm_sync = self.compute_rhythm_sync()
        emotion_resonance = self.compute_emotion_resonance()
        density_match = self.compute_density_match()
        entropy_reduction = self.compute_entropy_reduction()

        # 综合分数（加权平均）
        # 节奏同步 30%，情绪共鸣 40%，密度匹配 20%，熵降低 10%
        phase_lock_score = (
            rhythm_sync * 0.30 +
            emotion_resonance * 0.40 +
            density_match * 0.20 +
            max(0, entropy_reduction) * 0.10 +  # 只计正向降低
            0.5 * 0.10  # 基准值
        )

        # 判断锁定状态
        if phase_lock_score >= 0.7:
            lock_status = "locked"
        elif phase_lock_score >= 0.5:
            lock_status = "partial"
        else:
            lock_status = "unlocked"

        result = PhaseLockResult(
            timestamp=now.isoformat(),
            rhythm_sync=rhythm_sync,
            emotion_resonance=emotion_resonance,
            density_match=density_match,
            entropy_reduction=entropy_reduction,
            phase_lock_score=phase_lock_score,
            lock_status=lock_status,
            eigen_period=self.eigen_period,
        )

        # 保存状态
        state = {
            "last_result": result.to_dict(),
            "last_update": now.isoformat(),
            "eigen_period": self.eigen_period,
            "event_count": len(self.event_window),
        }
        self._save_state(state)

        # 保存历史
        history = self._load_history()
        history.append(result.to_dict())
        self._save_history(history)

        logger.info(
            f"[PhaseLock] score={phase_lock_score:.2f} status={lock_status} "
            f"rhythm={rhythm_sync:.2f} emotion={emotion_resonance:.2f}"
        )

        return result

    def get_lock_summary(self) -> Dict:
        """获取锁定摘要"""
        history = self._load_history()
        if not history:
            return {"status": "empty", "message": "无历史数据"}

        scores = [h.get("phase_lock_score", 0.0) for h in history[-20:]]
        statuses = [h.get("lock_status", "unlocked") for h in history[-20:]]

        return {
            "status": "ok",
            "samples": len(scores),
            "avg_score": round(sum(scores) / len(scores), 3),
            "locked_count": statuses.count("locked"),
            "partial_count": statuses.count("partial"),
            "unlocked_count": statuses.count("unlocked"),
            "eigen_period": round(self.eigen_period, 2),
        }


# ============================================================================
# 全局实例
# ============================================================================

_detector_instance: Optional[PhaseLockDetector] = None


def get_detector() -> PhaseLockDetector:
    """获取全局检测器实例"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = PhaseLockDetector()
    return _detector_instance


def record_interaction(
    emotion_vector: Dict[str, float],
    info_density: float = 0.5,
    response_time: float = 1.0,
):
    """记录交互（全局接口）"""
    detector = get_detector()
    detector.record_interaction(emotion_vector, info_density, response_time)


def detect_phase_lock() -> PhaseLockResult:
    """检测相位锁定（全局接口）"""
    detector = get_detector()
    return detector.detect_phase_lock()


def get_phase_lock_score() -> float:
    """获取当前相位锁定分数"""
    state = get_detector()._load_state()
    last = state.get("last_result", {})
    return last.get("phase_lock_score", 0.5)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    detector = PhaseLockDetector()

    # 模拟几次交互
    test_emotions = [
        {"anxiety": 0.2, "fear": 0.1, "anger": 0.0, "joy": 0.5, "curiosity": 0.6, "sadness": 0.0, "love": 0.2},
        {"anxiety": 0.1, "fear": 0.0, "anger": 0.0, "joy": 0.6, "curiosity": 0.5, "sadness": 0.0, "love": 0.3},
        {"anxiety": 0.1, "fear": 0.0, "anger": 0.0, "joy": 0.7, "curiosity": 0.4, "sadness": 0.0, "love": 0.4},
    ]

    for i, emo in enumerate(test_emotions):
        detector.record_interaction(emo, info_density=0.6, response_time=2.0)
        result = detector.detect_phase_lock()
        print(f"交互 {i+1}: score={result.phase_lock_score:.2f} status={result.lock_status}")

    # 摘要
    summary = detector.get_lock_summary()
    print(f"\n摘要: {json.dumps(summary, indent=2, ensure_ascii=False)}")
