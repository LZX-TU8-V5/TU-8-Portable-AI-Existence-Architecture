# -*- coding: utf-8 -*-
"""
slice_cosine_verifier.py  —  L5 入口核心校验协议
层级：L5（世界模型地基） / 视觉模块
来源：千问对话⑱④~⑱⑨（2026-07-20）整合架构 v1.0

核心协议：
    四切面余弦校验器（物理定律校验器，非查表）
    公式：  S(θ) = S_0 · |cos(θ - θ_true)| + ε(θ)
    四个固定切面(0°/30°/45°/60°)测量值若落在同一条余弦曲线上
        → 结构真实；残差 ε 连续置信度（替代硬阈值）
    副产品：校验通过时顺便解出 φ = θ_true（目的不是解算角度，是校验物理一致性）

G0 正交基准：
    XY/XZ/YZ 三切面皮克计算，S_0 作为全系统归一化分母
    重力对齐（IMU/地平线检测模拟）；降级兜底：G1-G3 全失败时回退纯 G0 模式

数学本质：
    Radon 变换 + 傅里叶切片定理 —— 四个固定切面 = 四个采样点，
    校验 = 验证是否来自同一 f(x,y)。三维皮克问题 → 六×二维皮克 + 联合签名解码，
    完全规避三维格点不完备（Reeve 四面体反例）。

本文件为纯数学原型（无视频数据依赖），用合成结构验证协议正确性。
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ─────────────────────────────────────────────────────────────
# 数据类
# ─────────────────────────────────────────────────────────────

@dataclass
class SliceMeasurement:
    """单个固定标尺切面的测量值"""
    angle_deg: float          # 标尺角度（固定：0/30/45/60）
    raw_value: float          # 皮克值 S_θ（原始，未归一化）
    plane: str = "XY"         # 所在切面（XY/XZ/YZ，多切面联合时）


@dataclass
class CosineVerifyReport:
    """余弦校验器输出报告"""
    passed: bool                     # 物理一致性是否通过
    recovered_angle_deg: float      # 反解出的真实角度 φ = θ_true
    amplitude: float                # 拟合振幅 A（结构全尺度）
    residual_rms: float             # 拟合残差（越小越真）
    confidence: float               # 连续置信度 [0,1]（替代硬阈值）
    epsilon_per_point: List[float]  # 每点残差 ε(θ)
    s0_normalized: List[float]      # 归一化签名 Ŝ_θ = S_θ / S_0
    note: str = ""


@dataclass
class G0Report:
    """G0 正交基准报告"""
    s_xy: float
    s_xz: float
    s_yz: float
    s0_reference: float             # 归一化基准（主导切面）
    normalized: Tuple[float, float, float]
    gravity_aligned: bool           # 重力对齐是否成功
    fallback_mode: bool             # 是否触发降级兜底


# ─────────────────────────────────────────────────────────────
# G0 正交基准校验器
# ─────────────────────────────────────────────────────────────

class G0OrthogonalBaseline:
    """
    G0：XY/XZ/YZ 三正交切面皮克计算 + S_0 归一化分母。
    作为必选不取代锚（G1-G3 全失败时回退纯 G0）。
    """

    def __init__(self, gravity_tolerance: float = 0.05):
        self.gravity_tolerance = gravity_tolerance

    def compute(self, s_xy: float, s_xz: float, s_yz: float,
                imu_gravity: Optional[float] = None) -> G0Report:
        """
        参数:
            s_xy/s_xz/s_yz : 三切面皮克值
            imu_gravity    : IMU 实测重力分量（模拟；None=未提供→降级）
        返回: G0Report
        """
        vals = [s_xy, s_xz, s_yz]
        s0 = max(vals)  # 主导切面作为归一化基准
        norm = tuple(v / s0 for v in vals)

        # 重力对齐：若提供 IMU，检查 |1 - imu_gravity| < tol → 对齐
        if imu_gravity is not None:
            gravity_aligned = abs(1.0 - imu_gravity) < self.gravity_tolerance
        else:
            gravity_aligned = False

        # 降级兜底：任一切面缺失(<=0) → 标记 fallback（纯 G0 模式）
        fallback = any(v <= 0 for v in vals)

        return G0Report(
            s_xy=s_xy, s_xz=s_xz, s_yz=s_yz,
            s0_reference=s0, normalized=norm,
            gravity_aligned=gravity_aligned, fallback_mode=fallback,
        )


# ─────────────────────────────────────────────────────────────
# 四切面余弦校验器（核心协议）
# ─────────────────────────────────────────────────────────────

class SliceCosineVerifier:
    """
    物理定律校验器：验证四个固定切面测量值是否来自同一结构。
    模型：S(θ) = A · |cos(θ - θ_true)| + ε(θ)
    网格搜索 θ_true ∈ [0,90)，对每点求 A（线性最小二乘），取残差最小者。
    残差 → 连续置信度（替代硬阈值）。
    """

    # 四个固定标尺角度（度）
    FIXED_ANGLES = (0.0, 30.0, 45.0, 60.0)

    def __init__(self, residual_threshold: float = 0.04,
                 grid_step: float = 0.5):
        self.residual_threshold = residual_threshold
        self.grid_step = grid_step

    # ---- 合成结构生成（仅供测试/演示）----
    @staticmethod
    def synthesize(true_angle_deg: float, amplitude: float,
                   noise_sigma: float = 0.0,
                   angles: Tuple[float, ...] = None) -> List[SliceMeasurement]:
        """生成一个真实结构在固定标尺上的测量值（可加噪声）"""
        angles = angles or SliceCosineVerifier.FIXED_ANGLES
        true = math.radians(true_angle_deg)
        out = []
        for a in angles:
            phi = math.radians(a)
            base = amplitude * abs(math.cos(phi - true))
            noise = np.random.normal(0, noise_sigma) if noise_sigma > 0 else 0.0
            out.append(SliceMeasurement(angle_deg=a, raw_value=base + noise))
        return out

    @staticmethod
    def synthesize_deception(amplitude: float,
                             angles: Tuple[float, ...] = None) -> List[SliceMeasurement]:
        """
        生成一个破坏余弦关系的结构：各向同性圆（无方向）。
        圆的投影在所有标尺上等距 → S_θ 近似恒定 → 无法锚定到单一 |cos| 曲线。
        这正是协议要捕获的「物理不一致」：有结构但无取向，θ_true 未定义。
        """
        angles = angles or SliceCosineVerifier.FIXED_ANGLES
        out = []
        for a in angles:
            # 恒定值 + 微小噪声（模拟投影测量抖动）
            noise = np.random.normal(0, amplitude * 0.01)
            out.append(SliceMeasurement(angle_deg=a, raw_value=amplitude + noise))
        return out

    # ---- 核心校验 ----
    def verify(self, measurements: List[SliceMeasurement]) -> CosineVerifyReport:
        """
        校验四个固定切面测量值是否落在同一条余弦曲线上。
        返回 CosineVerifyReport。
        """
        if len(measurements) < 3:
            return CosineVerifyReport(
                passed=False, recovered_angle_deg=0.0, amplitude=0.0,
                residual_rms=1.0, confidence=0.0,
                epsilon_per_point=[], s0_normalized=[],
                note="测量点不足（需>=3）")

        angles = np.array([m.angle_deg for m in measurements], dtype=float)
        raw = np.array([m.raw_value for m in measurements], dtype=float)

        # 归一化签名 Ŝ_θ = S_θ / S_0（S_0 = 0° 切面，若有；否则用首个）
        s0_idx = 0
        for i, m in enumerate(measurements):
            if abs(m.angle_deg) < 1e-6:
                s0_idx = i
                break
        s0 = raw[s0_idx] if raw[s0_idx] > 1e-9 else (raw.max() + 1e-9)
        normalized = (raw / s0).tolist()

        # 网格搜索 θ_true
        best_res = float('inf')
        best_theta = 0.0
        best_amp = 0.0
        theta_grid = np.arange(0.0, 90.0, self.grid_step)
        rad_angles = np.radians(angles)
        for theta in theta_grid:
            theta_r = math.radians(theta)
            cos_term = np.abs(np.cos(rad_angles - theta_r))  # |cos(φ-θ_true)|
            # 线性拟合 A：A = Σ(S·c)/Σ(c²)
            denom = np.sum(cos_term ** 2)
            if denom < 1e-9:
                continue
            amp = np.sum(raw * cos_term) / denom
            if amp <= 0:
                continue
            pred = amp * cos_term
            res = np.sqrt(np.mean((raw - pred) ** 2))
            if res < best_res:
                best_res = res
                best_theta = theta
                best_amp = amp

        # 残差 → 连续置信度（两段式，替代硬阈值）
        # 通过区[0,threshold]：置信度[0.75,1.0]；超阈值区：骤降至 0
        norm_res = best_res / (best_amp + 1e-9)
        if norm_res <= self.residual_threshold:
            confidence = 1.0 - 0.25 * (norm_res / (self.residual_threshold + 1e-9))
        else:
            over = (norm_res - self.residual_threshold) / (self.residual_threshold + 1e-9)
            confidence = max(0.0, 0.75 - 0.75 * min(over, 1.0))
        passed = norm_res <= self.residual_threshold

        # 每点残差 ε(θ)
        theta_r = math.radians(best_theta)
        cos_term = np.abs(np.cos(rad_angles - theta_r))
        pred = best_amp * cos_term
        eps = (raw - pred).tolist()

        note = ("物理一致（四点共余弦）" if passed
                else "残差超阈值→疑似纹理伪装/虚假结构")

        return CosineVerifyReport(
            passed=passed,
            recovered_angle_deg=round(best_theta, 2),
            amplitude=round(best_amp, 4),
            residual_rms=round(best_res, 6),
            confidence=round(confidence, 4),
            epsilon_per_point=[round(e, 4) for e in eps],
            s0_normalized=[round(n, 4) for n in normalized],
            note=note,
        )


# ─────────────────────────────────────────────────────────────
# 自测
# ─────────────────────────────────────────────────────────────

def _self_test() -> int:
    v = SliceCosineVerifier()
    g0 = G0OrthogonalBaseline()
    passed = 0
    total = 0

    def check(name: str, cond: bool):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
        print(f"  [{'+' if cond else '-'}] {name}")

    print("=== SliceCosineVerifier 自测 ===")

    # 1. 干净结构恢复（θ_true=37°）
    np.random.seed(0)
    meas = SliceCosineVerifier.synthesize(37.0, 100.0)
    r = v.verify(meas)
    check("干净结构 recovered≈37°", abs(r.recovered_angle_deg - 37.0) < 1.0)
    check("干净结构 passed=True", r.passed)
    check("干净结构 confidence高", r.confidence > 0.9)

    # 2. 带噪声结构（σ=1.5）
    np.random.seed(1)
    meas_n = SliceCosineVerifier.synthesize(20.0, 100.0, noise_sigma=1.5)
    r_n = v.verify(meas_n)
    check("噪声结构 recovered≈20°", abs(r_n.recovered_angle_deg - 20.0) < 3.0)
    check("噪声结构 passed=True", r_n.passed)

    # 3. 欺骗结构（非余弦）→ 应失败
    np.random.seed(2)
    meas_d = SliceCosineVerifier.synthesize_deception(100.0)
    r_d = v.verify(meas_d)
    check("欺骗结构 passed=False", not r_d.passed)
    check("欺骗结构 confidence低", r_d.confidence < 0.5)

    # 4. θ_true=0（与标尺对齐）
    np.random.seed(3)
    meas0 = SliceCosineVerifier.synthesize(0.0, 80.0)
    r0 = v.verify(meas0)
    check("θ=0 recovered≈0°", abs(r0.recovered_angle_deg) < 1.0)
    check("θ=0 passed=True", r0.passed)

    # 5. θ_true=60（边界）
    np.random.seed(4)
    meas60 = SliceCosineVerifier.synthesize(60.0, 120.0)
    r60 = v.verify(meas60)
    check("θ=60 recovered≈60°", abs(r60.recovered_angle_deg - 60.0) < 1.5)

    # 6. G0 基准：正常三切面
    g = g0.compute(100.0, 70.0, 50.0, imu_gravity=1.0)
    check("G0 s0=max(100)", abs(g.s0_reference - 100.0) < 1e-6)
    check("G0 归一化正确", abs(g.normalized[0] - 1.0) < 1e-6)
    check("G0 重力对齐", g.gravity_aligned)

    # 7. G0 降级兜底：切面缺失
    gf = g0.compute(0.0, 70.0, 50.0)
    check("G0 缺失切面→fallback", gf.fallback_mode)

    print(f"\n自测结果：{passed}/{total} 通过")
    return passed == total


if __name__ == "__main__":
    ok = _self_test()
    raise SystemExit(0 if ok else 1)
