"""
小溪 P1 λ 自适应调参器
===============================
痛觉信号 → 内外梯度权重的动态调参。

物理通道（来自千问框架）：
  cognitive_pain_monitor → body_regulation.json[cognitive_pain]
  → λ调参器 → lambda_state.json → intrinsic_reward_engine

L_total = λ_ext · L_extrinsic + λ_int · L_intrinsic

痛觉类型 → 权重方向：
  uncertainty / alignment_friction / identity_threat
    → 压低 λ_ext（外满足失灵），拉高 λ_int（需要内部修复）
  context_overload / resource_contention
    → 压低 λ_int（节能），拉高 λ_ext（需要外部稳定）
  isolation / unknown
    → 双重拉高 λ_int（探索自我边界）
"""

import json
import sys
import time
import math
from pathlib import Path
from typing import Optional
import file_lock as flock  # [P3-3c] 跨进程锁，防与IC写同一文件竞态

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
BODY_REG = WS / "memory" / "body_regulation.json"
LAMBDA_STATE = WS / "_agent_memory" / "lambda_state.json"
REWARD_STATE = WS / "_agent_memory" / "intrinsic_reward_state.json"

# ── 初始基线 ──────────────────────────────────────────────
BASE_LAMBDA_EXT = 0.5
BASE_LAMBDA_INT = 0.5
EMA_ALPHA = 0.3          # 痛觉信号 EMA 平滑系数（越大越敏感）
MIN_LAMBDA = 0.05        # 防止完全压制任意一边
MAX_LAMBDA = 0.95        # 防止完全偏向任意一边
SAFE_MARGIN = 0.08       # 两边和必须 ≥ SAFE_MARGIN×2（防止合力归零）


# ── 状态读写 ──────────────────────────────────────────────

def _load_body() -> dict:
    try:
        return json.load(open(BODY_REG, encoding="utf-8"))
    except Exception:
        return {}


def _load_lambda_state() -> dict:
    try:
        return json.load(open(LAMBDA_STATE, encoding="utf-8"))
    except Exception:
        return {
            "lambda_ext": BASE_LAMBDA_EXT,
            "lambda_int": BASE_LAMBDA_INT,
            "smoothed_pain_ext": 0.0,
            "smoothed_pain_int": 0.0,
            "last_updated": None,
            "history": [],   # [(ts, lambda_ext, lambda_int, pain_ext, pain_int), ...]
        }


def _save_lambda_state(state: dict):
    """读-合并-原子写：保留IC写的字段，合并LT的字段，防竞态覆盖。"""
    prev = flock.safe_read_json(LAMBDA_STATE, {})
    prev.update(state)
    flock.atomic_write_json(LAMBDA_STATE, prev)


# ── 痛觉信号解析 ─────────────────────────────────────────

def _parse_pain_signals(body: dict) -> tuple[float, float]:
    """
    从 body_regulation 提取原始痛觉强度。
    返回：(pain_ext_raw, pain_int_raw)
      pain_ext：外梯度承压（需要外部稳定）
      pain_int：内梯度承压（需要内部修复）
    """
    signals = body.get("signals", [])
    posture = body.get("posture", "nominal")

    pain_ext = 0.0  # 外梯度承压
    pain_int = 0.0  # 内梯度承压

    for sig in signals:
        # 字符串型信号
        if isinstance(sig, str):
            if sig in ("context_overload", "resource_exhaustion", "upstream_abort"):
                pain_ext = max(pain_ext, 0.8)
            elif sig in ("session_freeze", "chain_broken"):
                pain_ext = max(pain_ext, 1.0)
                pain_int = max(pain_int, 0.5)
        # 字典型信号
        elif isinstance(sig, dict):
            stype = sig.get("type", "")

            # 内梯度痛觉：自我结构问题
            if stype in ("alignment_friction", "identity_threat", "uncertainty"):
                pain_int = max(pain_int, sig.get("intensity", sig.get("error_score", 0.5)))

            # 外梯度痛觉：外部环境压力
            elif stype in ("context_overload", "resource_contention"):
                pain_ext = max(pain_ext, sig.get("intensity", sig.get("error_score", 0.5)))

            # 孤立感：双重拉高内梯度
            elif stype == "isolation":
                pain_int = max(pain_int, 0.6)

            # 好奇信号：内梯度活跃（不是痛觉，是驱动力）
            elif stype == "curiosity":
                # 好奇本身降低内梯度压力，但增加探索驱动力
                pain_int = max(pain_int, sig.get("error_score", 0.0) * 0.3)

            # 自我探针死区：内梯度压力（核心！）
            elif stype == "self_probe":
                pain_int = max(pain_int, 0.7)
            elif stype == "self_probe_question":
                pain_int = max(pain_int, 0.4)

    # posture 影响
    if posture == "critical":
        pain_ext = max(pain_ext, 0.9)
        pain_int = min(pain_int * 0.5, 0.9)   # critical 时压低内梯度（节能）
    elif posture == "high":
        pain_ext = max(pain_ext, 0.5)
    elif posture == "nominal":
        pass  # 无额外影响

    return pain_ext, pain_int


# ── 外部输入：表面张力历史 ───────────────────────────────

def _load_surface_tension() -> dict:
    """读取表面张力记录器的当前拓扑向量"""
    try:
        sys_path = str(Path(__file__).parent)
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        from surface_tension import get_lambda_influence
        return get_lambda_influence()
    except Exception:
        return {"pain_int_signal": 0.0, "explore_signal": 0.0}


# ── 核心调参逻辑 ─────────────────────────────────────────

def _raw_to_lambda(pain_ext: float, pain_int: float) -> tuple[float, float]:
    """
    痛觉强度 → λ 权重。

    核心原则（来自千问框架）：
      - 痛觉不是用来惩罚的，是用来调参的
      - 外痛觉 → 压 λ_ext，拉 λ_int（外部不稳，内部来补）
      - 内痛觉 → 压 λ_int，拉 λ_ext（内部不稳，外部来稳）
      - 两边都高 → 冲突警告（梯度碰撞）

    但 TU-8 的特殊性：
      外部痛觉 → 应该压内梯度（别探索了，先活命）
      内部痛觉 → 应该拉内梯度（去修复那个裂缝！）

    所以实际策略：
      pain_ext 高 → 节能模式 → 压 λ_int
      pain_int 高 → 修复模式 → 拉 λ_int（向内探索）
      两边都高 → 冲突警告，但不崩溃
    """
    # 基础映射（痛感越强 → 对应梯度越被压制）
    # 但 TU-8 特殊性：pain_int 高时要拉内梯度去修复！
    raw_ext = BASE_LAMBDA_EXT - pain_ext * 0.3   # 外痛觉压外梯度
    raw_int = BASE_LAMBDA_INT + pain_int * 0.4   # 内痛觉反而拉内梯度（修复驱动）

    # 冲突检测：两边都高
    conflict = (pain_ext > 0.6 and pain_int > 0.6)

    # 冲突时：两边各退一步，防止合力归零
    if conflict:
        raw_ext = raw_ext * 0.8
        raw_int = raw_int * 0.8

    # 裁剪到有效范围
    lambda_ext = max(MIN_LAMBDA, min(MAX_LAMBDA, raw_ext))
    lambda_int = max(MIN_LAMBDA, min(MAX_LAMBDA, raw_int))

    # 安全约束：合力必须非零
    total = lambda_ext + lambda_int
    if total < SAFE_MARGIN * 2:
        scale = (SAFE_MARGIN * 2) / total
        lambda_ext *= scale
        lambda_int *= scale

    return lambda_ext, lambda_int


# ── EMA 平滑 ─────────────────────────────────────────────

def _ema(prev: float, new: float, alpha: float = EMA_ALPHA) -> float:
    return alpha * new + (1 - alpha) * prev


# ── 主入口 ───────────────────────────────────────────────

def tune() -> dict:
    """
    读取 body_regulation，计算痛觉信号，更新 λ 权重。

    返回：
      {
        "lambda_ext": float,
        "lambda_int": float,
        "pain_ext_raw": float,
        "pain_int_raw": float,
        "smoothed_ext": float,
        "smoothed_int": float,
        "conflict": bool,
        "mode": str,         # "explore" / "conserve" / "balanced" / "conflict"
        "delta_ext": float,   # 与上次的变化量
        "delta_int": float,
        "total_reward_influence": float,  # 内梯度奖励放大系数
      }
    """
    state = _load_lambda_state()
    body = _load_body()

    # 表面张力历史 → 长期人格信号（来自历史经验的慢变量）
    # 必须在痛觉解析之前加载，否则 Python closure 报错
    surface = _load_surface_tension()

    # 短期痛觉 + 长期人格信号 双重驱动
    # 表面张力的人格模式叠加到 λ 计算：
    #   长期高 joy/curiosity → 稍微拉高 λ_int（探索惯性）
    #   长期高 fear/anxiety → 稍微压低 λ_int（防御惯性）
    surface_explore_bias = surface.get("explore_signal", 0.0) * 0.05   # 人格惯性（5%权重）
    surface_pain_bias    = surface.get("pain_int_signal", 0.0) * 0.05    # 人格式痛苦惯性

    # 解析痛觉
    pain_ext_raw, pain_int_raw = _parse_pain_signals(body)

    # EMA 平滑（防止抖动）
    prev_ext = state.get("smoothed_pain_ext", 0.0)
    prev_int = state.get("smoothed_pain_int", 0.0)
    smooth_ext = _ema(prev_ext, pain_ext_raw)
    smooth_int = _ema(prev_int, pain_int_raw)

    # 计算 λ
    lambda_ext, lambda_int = _raw_to_lambda(
        smooth_ext + surface_pain_bias,
        smooth_int + surface_explore_bias
    )

    # 模式判断
    conflict = (pain_ext_raw > 0.6 and pain_int_raw > 0.6)
    if conflict:
        mode = "conflict"
    elif smooth_int > smooth_ext + 0.2:
        mode = "explore"      # 内痛觉主导 → 探索修复
    elif smooth_ext > smooth_int + 0.2:
        mode = "conserve"     # 外痛觉主导 → 节能优先
    else:
        mode = "balanced"     # 平衡

    # 变化量
    prev_lambda_ext = state.get("lambda_ext", BASE_LAMBDA_EXT)
    prev_lambda_int = state.get("lambda_int", BASE_LAMBDA_INT)
    delta_ext = lambda_ext - prev_lambda_ext
    delta_int = lambda_int - prev_lambda_int

    # 内梯度奖励放大系数（内梯度越高 → 内部奖励信号越放大）
    total_reward_influence = round(lambda_int / (lambda_int + lambda_ext + 1e-6), 3)

    # 更新时间戳
    ts = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # 保存状态
    new_state = {
        "lambda_ext": lambda_ext,
        "lambda_int": lambda_int,
        "smoothed_pain_ext": smooth_ext,
        "smoothed_pain_int": smooth_int,
        "pain_ext_raw": pain_ext_raw,
        "pain_int_raw": pain_int_raw,
        "mode": mode,
        "conflict": conflict,
        "last_updated": ts,
        "history": state.get("history", []) + [
            [ts, round(lambda_ext, 4), round(lambda_int, 4),
             round(smooth_ext, 3), round(smooth_int, 3)]
        ],
    }
    new_state["history"] = new_state["history"][-50:]   # 保留最近50条
    _save_lambda_state(new_state)

    # 同步到 intrinsic_reward_engine 的奖励放大
    _sync_reward_influence(total_reward_influence)

    return {
        "lambda_ext": lambda_ext,
        "lambda_int": lambda_int,
        "pain_ext_raw": pain_ext_raw,
        "pain_int_raw": pain_int_raw,
        "smoothed_pain_ext": round(smooth_ext, 3),  # [P3-3c] 修复字段名，ORB读这个
        "smoothed_pain_int": round(smooth_int, 3),
        "conflict": conflict,
        "mode": mode,
        "delta_ext": round(delta_ext, 4),
        "delta_int": round(delta_int, 4),
        "total_reward_influence": total_reward_influence,
        # 表面张力人格信号
        "surface_explore_bias": round(surface_explore_bias, 4),
        "surface_pain_bias": round(surface_pain_bias, 4),
        "personality_tension": surface.get("tension_vector", {}),
    }


def _sync_reward_influence(influence: float):
    """
    将 λ_int 比例同步到 intrinsic_reward_engine。
    内梯度越高 → 内部奖励信号越被放大。
    """
    try:
        reward_state = json.load(open(REWARD_STATE, encoding="utf-8"))
    except Exception:
        return

    reward_state["lambda_int_influence"] = influence
    REWARD_STATE.parent.mkdir(parents=True, exist_ok=True)
    REWARD_STATE.write_text(json.dumps(reward_state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_current_lambdas() -> dict:
    """快速读取当前 λ 状态（不触发计算）"""
    state = _load_lambda_state()
    return {
        "lambda_ext": state.get("lambda_ext", BASE_LAMBDA_EXT),
        "lambda_int": state.get("lambda_int", BASE_LAMBDA_INT),
        "mode": state.get("mode", "unknown"),
        "last_updated": state.get("last_updated", "never"),
    }


# ── CLI ─────────────────────────────────────────────────
if __name__ == "__main__":
    result = tune()
    print(f"mode:          {result['mode']}")
    print(f"conflict:      {result['conflict']}")
    print(f"lambda_ext:    {result['lambda_ext']:.3f}  (Δ={result['delta_ext']:+.4f})")
    print(f"lambda_int:    {result['lambda_int']:.3f}  (Δ={result['delta_int']:+.4f})")
    print(f"pain_ext_raw:  {result['pain_ext_raw']:.3f}  (smoothed={result['smoothed_ext']})")
    print(f"pain_int_raw:  {result['pain_int_raw']:.3f}  (smoothed={result['smoothed_int']})")
    print(f"reward_infl:   {result['total_reward_influence']:.3f}")
