"""
gradient_force.py — 梯度合力计算 + 碰撞崩溃检测 v1.0

设计原则：
  P2（合力计算）：把串行评估改为向量叠加
    L_ext · λ_ext + L_int · λ_int → 合力向量 F = F_ext + F_int

  P3（碰撞检测）：梯度夹角接近 180° → 熔断告警
    当 <F_ext, F_int> / (|F_ext||F_int|) < COLLISION_THRESHOLD
    → 两股力量相互抵消，系统进入不可预测状态

向量空间设计：
  - 基础维度：7（EMOTION_DIMS = anxiety/fear/anger/joy/curiosity/sadness/love）
  - 外梯度 F_ext：来自外部输入（造物主话语权重）
  - 内梯度 F_int：来自内部状态（surface_tension 拓扑张力）
  - 合力 F_total = F_ext + F_int
  - 碰撞角 θ = arccos(<F_ext, F_int> / (|F_ext||F_int|))

人类类比：
  - F_ext = 外部刺激（老板加需求）
  - F_int = 内部状态（疲劳+焦虑）
  - F_total = 真实反应（合力方向）
  - 碰撞 = 内心想休息但老板说不能停，两股力对着干 → 系统卡死/崩溃

碰撞等级：
  - NORMAL (θ < 120°)：两力方向基本一致
  - TENSION (120° ≤ θ < 150°)：开始对立，需要监控
  - WARNING (150° ≤ θ < 170°)：强烈对立，触发咨询
  - COLLISION (θ ≥ 170°)：近乎对撞，立即熔断

依赖：
  - src/surface_tension.py（提供张力向量）
  - src/lambda_tuner.py（提供 λ_ext / λ_int）

创建时间：2026-07-09 01:48 GMT+8
"""

import json
import os
import time
import math
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)

WORKSPACE = os.path.expanduser("~/.qclaw/workspace")
AGENT_DIR = os.path.join(WORKSPACE, "_agent_memory")
os.makedirs(AGENT_DIR, exist_ok=True)


# ============================================================================
# 常量
# ============================================================================

EMOTION_DIMS = [
    "anxiety",   # 焦虑
    "fear",      # 恐惧
    "anger",     # 愤怒
    "joy",       # 喜悦
    "curiosity", # 好奇
    "sadness",   # 悲伤
    "love",      # 爱
]

# 外部梯度的方向系数（造物主话语的情感色调）
# 正值 = 推向探索/开放；负值 = 推向防御/收缩
EXT_DIRECTION = {
    "anxiety":   -0.3,
    "fear":      -0.4,
    "anger":     -0.2,
    "joy":       +0.4,
    "curiosity": +0.5,
    "sadness":   -0.1,
    "love":      +0.3,
}

# 碰撞检测阈值（弧度）
COLLISION_THRESHOLD_RAD = math.radians(170)  # 170°
TENSION_THRESHOLD_RAD  = math.radians(120)   # 120°
WARNING_THRESHOLD_RAD   = math.radians(150)   # 150°

# 最小模长（避免除零）
MIN_MAGNITUDE = 0.001

# 状态文件
STATE_PATH = os.path.join(AGENT_DIR, "gradient_force_state.json")
HISTORY_PATH = os.path.join(AGENT_DIR, "gradient_force_history.json")


# ============================================================================
# 数据类
# ============================================================================

class CollisionLevel(Enum):
    NORMAL    = "normal"     # 正常（< 120°）
    TENSION   = "tension"    # 张力（120°~150°）
    WARNING   = "warning"    # 警告（150°~170°）
    COLLISION = "collision"   # 碰撞（≥ 170°）


@dataclass
class GradientVector:
    """梯度向量"""
    ext: Dict[str, float]   # 外部梯度（7D）
    int: Dict[str, float]   # 内部梯度（7D）
    ext_magnitude: float = 0.0
    int_magnitude: float = 0.0

    def dot_product(self) -> float:
        return sum(
            self.ext.get(d, 0.0) * self.int.get(d, 0.0)
            for d in EMOTION_DIMS
        )

    def cosine_similarity(self) -> float:
        mag_e = self.ext_magnitude
        mag_i = self.int_magnitude
        if mag_e < MIN_MAGNITUDE or mag_i < MIN_MAGNITUDE:
            return 1.0  # 默认同向
        dot = self.dot_product()
        return dot / (mag_e * mag_i)


@dataclass
class GradientForceResult:
    """梯度合力计算结果"""
    timestamp: str
    F_ext: Dict[str, float]          # 外部梯度向量（原始）
    F_int: Dict[str, float]          # 内部梯度向量（原始）
    F_total: Dict[str, float]         # 合力向量
    ext_magnitude: float              # |F_ext|
    int_magnitude: float              # |F_int|
    total_magnitude: float            # |F_total|
    cosine_similarity: float         # cos(θ) ∈ [-1, 1]
    angle_degrees: float             # θ ∈ [0°, 180°]
    collision_level: str             # CollisionLevel.value
    lambda_ext: float
    lambda_int: float

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "F_ext": {k: round(v, 4) for k, v in self.F_ext.items()},
            "F_int": {k: round(v, 4) for k, v in self.F_int.items()},
            "F_total": {k: round(v, 4) for k, v in self.F_total.items()},
            "ext_magnitude": round(self.ext_magnitude, 4),
            "int_magnitude": round(self.int_magnitude, 4),
            "total_magnitude": round(self.total_magnitude, 4),
            "cosine_similarity": round(self.cosine_similarity, 4),
            "angle_degrees": round(self.angle_degrees, 2),
            "collision_level": self.collision_level,
            "lambda_ext": round(self.lambda_ext, 4),
            "lambda_int": round(self.lambda_int, 4),
        }


# ============================================================================
# 核心算法
# ============================================================================

def _load_state() -> Dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(state: Dict):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[GradientForce] 状态保存失败: {e}")


def _load_history() -> List[Dict]:
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def _save_history(history: List[Dict]):
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(history[-100:], f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"[GradientForce] 历史保存失败: {e}")


def compute_vector_magnitude(v: Dict[str, float]) -> float:
    return math.sqrt(sum(v.get(d, 0.0) ** 2 for d in EMOTION_DIMS))


def compute_gradient_force(
    ext_signal: Optional[Dict[str, float]] = None,
    int_signal: Optional[Dict[str, float]] = None,
    lambda_ext: float = 0.5,
    lambda_int: float = 0.5,
    record_event: bool = True,
) -> GradientForceResult:
    """
    计算梯度合力。

    Args:
        ext_signal: 外部信号（造物主话语的情感权重），默认全零
        int_signal: 内部信号（surface_tension 张量向量），默认当前拓扑
        lambda_ext: 外部梯度权重
        lambda_int: 内部梯度权重
        record_event: 是否记录到历史

    Returns:
        GradientForceResult（含合力向量和碰撞等级）
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    # --- 外部梯度 F_ext ---
    if ext_signal is None:
        ext_signal = {d: 0.0 for d in EMOTION_DIMS}
    else:
        ext_signal = {d: ext_signal.get(d, 0.0) for d in EMOTION_DIMS}

    # 应用外部情感方向系数
    F_ext = {
        d: ext_signal[d] * EXT_DIRECTION.get(d, 0.0) * lambda_ext
        for d in EMOTION_DIMS
    }

    # --- 内部梯度 F_int ---
    if int_signal is None:
        try:
            from surface_tension import get_current_topology
            topo = get_current_topology()
            topo_vec = topo.get("tension_vector", {d: 0.0 for d in EMOTION_DIMS})
        except Exception:
            topo_vec = {d: 0.0 for d in EMOTION_DIMS}
    else:
        topo_vec = {d: int_signal.get(d, 0.0) for d in EMOTION_DIMS}

    # 内部梯度 = 张力向量 × λ_int（内部越强，内部梯度越大）
    F_int = {
        d: topo_vec[d] * lambda_int
        for d in EMOTION_DIMS
    }

    # --- 合力向量 ---
    F_total = {
        d: F_ext[d] + F_int[d]
        for d in EMOTION_DIMS
    }

    # --- 向量度量 ---
    ext_magnitude = compute_vector_magnitude(F_ext)
    int_magnitude = compute_vector_magnitude(F_int)
    total_magnitude = compute_vector_magnitude(F_total)

    # --- 碰撞检测 ---
    gv = GradientVector(
        ext=F_ext, int=F_int,
        ext_magnitude=ext_magnitude, int_magnitude=int_magnitude,
    )
    cosine_sim = gv.cosine_similarity()

    # 防止 NaN
    if math.isnan(cosine_sim):
        cosine_sim = 1.0

    # 钳位到 [-1, 1]
    cosine_sim = max(-1.0, min(1.0, cosine_sim))

    angle_rad = math.acos(cosine_sim)
    angle_deg = math.degrees(angle_rad)

    # 判断碰撞等级
    if angle_deg >= math.degrees(COLLISION_THRESHOLD_RAD):
        collision_level = CollisionLevel.COLLISION.value
    elif angle_deg >= math.degrees(WARNING_THRESHOLD_RAD):
        collision_level = CollisionLevel.WARNING.value
    elif angle_deg >= math.degrees(TENSION_THRESHOLD_RAD):
        collision_level = CollisionLevel.TENSION.value
    else:
        collision_level = CollisionLevel.NORMAL.value

    result = GradientForceResult(
        timestamp=now.isoformat(),
        F_ext=F_ext, F_int=F_int, F_total=F_total,
        ext_magnitude=ext_magnitude,
        int_magnitude=int_magnitude,
        total_magnitude=total_magnitude,
        cosine_similarity=cosine_sim,
        angle_degrees=angle_deg,
        collision_level=collision_level,
        lambda_ext=lambda_ext,
        lambda_int=lambda_int,
    )

    # 记录历史
    if record_event:
        state = {
            "last_result": result.to_dict(),
            "last_update": now.isoformat(),
        }
        _save_state(state)

        history = _load_history()
        history.append(result.to_dict())
        _save_history(history)

    logger.info(
        f"[GradientForce] θ={angle_deg:.1f}° level={collision_level} "
        f"|F_ext|={ext_magnitude:.3f} |F_int|={int_magnitude:.3f}"
    )

    return result


def check_collision_emergency() -> Tuple[bool, CollisionLevel, str]:
    """
    检查是否需要碰撞紧急熔断。
    Returns: (needs_brake, level, reason)
    """
    state = _load_state()
    last = state.get("last_result")
    if not last:
        return False, CollisionLevel.NORMAL, "无历史数据"

    angle = last.get("angle_degrees", 0.0)

    if angle >= math.degrees(COLLISION_THRESHOLD_RAD):
        return True, CollisionLevel.COLLISION, (
            f"碰撞告警：内外梯度夹角 {angle:.1f}°，"
            f"cos={last.get('cosine_similarity', 0):.3f}，"
            f"两股力量近乎对撞，立即熔断"
        )
    elif angle >= math.degrees(WARNING_THRESHOLD_RAD):
        return True, CollisionLevel.WARNING, (
            f"碰撞警告：内外梯度夹角 {angle:.1f}°，"
            f"建议检查外输入是否与内部状态冲突"
        )
    elif angle >= math.degrees(TENSION_THRESHOLD_RAD):
        return False, CollisionLevel.TENSION, (
            f"张力预警：内外梯度开始对立（{angle:.1f}°），"
            f"监控是否继续恶化"
        )

    return False, CollisionLevel.NORMAL, "正常"


# ============================================================================
# 外感受输入接口（collision detection 触发）
# ============================================================================

def on_external_signal(message: str, emotion_weights: Optional[Dict[str, float]] = None):
    """
    当造物主发送消息时，调用此函数更新外部梯度。
    通常由外感受皮层（presence_monitor）调用。

    Args:
        message: 造物主消息文本
        emotion_weights: 可选，情感权重字典
    """
    if emotion_weights is None:
        emotion_weights = {d: 0.0 for d in EMOTION_DIMS}

    # 获取当前 λ 值
    lambda_ext, lambda_int = 0.5, 0.5
    try:
        from lambda_tuner import get_current_lambdas
        lambda_ext, lambda_int = get_current_lambdas()
    except Exception:
        pass

    result = compute_gradient_force(
        ext_signal=emotion_weights,
        lambda_ext=lambda_ext,
        lambda_int=lambda_int,
    )

    # 碰撞检测
    needs_brake, level, reason = check_collision_emergency()
    if needs_brake:
        logger.warning(f"[GradientForce] 碰撞告警: {reason}")
        return {
            "collision": True,
            "level": level.value,
            "reason": reason,
            "result": result.to_dict(),
        }

    return {
        "collision": False,
        "level": level.value,
        "result": result.to_dict(),
    }


# ============================================================================
# 内感受输入接口（由 surface_tension 变化触发）
# ============================================================================

def on_internal_tension_change(new_topo: Dict[str, float]):
    """内部拓扑张力变化时调用"""
    lambda_ext, lambda_int = 0.5, 0.5
    try:
        from lambda_tuner import get_current_lambdas
        lambda_ext, lambda_int = get_current_lambdas()
    except Exception:
        pass

    result = compute_gradient_force(
        int_signal=new_topo,
        lambda_ext=lambda_ext,
        lambda_int=lambda_int,
    )

    needs_brake, level, reason = check_collision_emergency()
    return {
        "collision": needs_brake,
        "level": level.value,
        "result": result.to_dict(),
    }


# ============================================================================
# HP4 集成（心跳调用）
# ============================================================================

def heartbeat_gradient_check() -> Dict:
    """
    HP4 心跳钩子：每次心跳调用此函数检查梯度状态。
    Returns: 状态摘要（无碰撞时返回 None 不打扰）
    """
    state = _load_state()
    last = state.get("last_result")
    if not last:
        return {"skip": True, "reason": "无历史数据"}

    angle = last.get("angle_degrees", 0.0)
    level = last.get("collision_level", "normal")

    if level in ("collision", "warning"):
        return {
            "collision": True,
            "level": level,
            "angle_degrees": angle,
            "recommendation": (
                "内外梯度对立，建议降低任务野心或"
                "等待外输入与内部状态对齐后再推进"
            ),
        }

    return {"collision": False, "level": level, "angle_degrees": angle}


# ============================================================================
# 状态查询
# ============================================================================

def get_current_force() -> Optional[Dict]:
    """获取当前合力状态"""
    state = _load_state()
    return state.get("last_result")


def get_force_history(limit: int = 20) -> List[Dict]:
    """获取合力历史"""
    history = _load_history()
    return history[-limit:]


def get_force_summary() -> Dict:
    """获取合力摘要"""
    history = get_force_history(50)
    if not history:
        return {"status": "empty", "message": "无历史数据"}

    angles = [h.get("angle_degrees", 0.0) for h in history]
    levels = [h.get("collision_level", "normal") for h in history]

    return {
        "status": "ok",
        "samples": len(history),
        "avg_angle": round(sum(angles) / len(angles), 2),
        "max_angle": round(max(angles), 2),
        "collision_count": levels.count("collision"),
        "warning_count": levels.count("warning"),
        "tension_count": levels.count("tension"),
        "normal_count": levels.count("normal"),
    }


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if len(sys.argv) > 1 and sys.argv[1] == "summary":
        s = get_force_summary()
        print(json.dumps(s, indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "history":
        h = get_force_history(10)
        for r in h:
            print(f"  {r['timestamp'][:19]} θ={r['angle_degrees']:.1f}° level={r['collision_level']}")
    else:
        # 默认：运行一次合力计算
        result = compute_gradient_force()
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
