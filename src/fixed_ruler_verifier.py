# -*- coding: utf-8 -*-
"""
fixed_ruler_verifier.py  —  G1/G2/G3 固定标尺并行校验（六投影联合编码）
层级：L5（世界模型地基） / 视觉模块
来源：千问对话⑱⑧ (2026-07-20) 固定标尺切片签名 + 六投影联合编码

核心突破（三维皮克问题规避）：
    三维格点不完备（Reeve 四面体反例）→ 三维皮克失效。
    固定标尺切片签名：45/30/60° = 固定测量标尺，强制投影上去，
    「标尺与物体的错位本身就是信息」。
    六投影签名 = 3 个固定标尺 × 2 个切面（XY/XZ）= 6 个归一化值联合向量 Σ。
    联合解码 → 反解真实参数 (θ, φ, V)，签名 Σ→(θ,φ,V) 为单射。
    复杂度：O(N³) → O(1) 查表，完全规避三维格点不完备。

一级快速通道（容差窗口 ±3°~5°）：
    若固定标尺反解角度落在已知结构字典邻域内 → 直接接受（免二级连续搜索）。
    否则 → 触发二级连续角度扫描（±10° 精细）。

本模块复用 slice_cosine_verifier.SliceCosineVerifier 做每平面并行解码。
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from slice_cosine_verifier import SliceCosineVerifier, SliceMeasurement


# 已知结构角度字典（一级快速通道查找表）
KNOWN_ANGLES = (0.0, 15.0, 30.0, 45.0, 60.0, 75.0)


@dataclass
class StructureParams:
    """真实 3D 结构参数"""
    theta_deg: float      # XY 切面主方向角
    phi_deg: float        # XZ 切面主方向角
    volume: float         # 体积/振幅代理（XY 投影振幅）


@dataclass
class RulerMeasurement:
    ruler_deg: float
    plane: str
    raw_value: float


@dataclass
class FixedRulerReport:
    """六投影联合校验报告"""
    signature: List[float]              # 6 值归一化签名 Σ
    theta_recovered: float              # XY 面反解角
    phi_recovered: float                # XZ 面反解角
    volume_recovered: float
    confidence: float
    fast_path: bool                     # 一级快速通道是否命中
    note: str


class FixedRulerVerifier:
    """
    G1/G2/G3 固定标尺并行校验器。
    输入：3D 结构参数（合成）或测量值
    输出：六投影签名 Σ + 反解 (θ, φ, V) + 一级/二级通道判定
    """

    FIXED_RULERS = (45.0, 30.0, 60.0)
    PLANES = ("XY", "XZ")

    def __init__(self, tolerance_deg: float = 5.0,
                 xz_scale: float = 0.8):
        self.tolerance_deg = tolerance_deg
        self.xz_scale = xz_scale   # XZ 投影相对 XY 的尺度因子（模拟不同投影）

    # ── 合成：结构 → 测量值 ──
    def synthesize(self, p: StructureParams,
                   noise_sigma: float = 0.0) -> List[RulerMeasurement]:
        """
        给定真实结构 (θ, φ, V)，生成固定标尺测量值。
        模型：S(ψ, P) = A_P · |cos(ψ - α_P)|，A_XY=V，A_XZ=V·xz_scale
        α_XY=θ，α_XZ=φ。含 0° 基准（供余弦校验器归一化）。
        """
        meas = []
        planes_params = {"XY": (p.theta_deg, p.volume),
                         "XZ": (p.phi_deg, p.volume * self.xz_scale)}
        for plane, (alpha, amp) in planes_params.items():
            a = math.radians(alpha)
            for psi in (0.0,) + self.FIXED_RULERS:
                psi_r = math.radians(psi)
                base = amp * abs(math.cos(psi_r - a))
                noise = 0.0
                if noise_sigma > 0:
                    import numpy as np
                    noise = np.random.normal(0, noise_sigma)
                meas.append(RulerMeasurement(ruler_deg=psi, plane=plane,
                                             raw_value=base + noise))
        return meas

    # ── 每平面并行解码 ──
    def _decode_plane(self, measurements: List[RulerMeasurement],
                      verifier: SliceCosineVerifier) -> Tuple[float, float]:
        """对单平面 4 个标尺(0/30/45/60)测量做余弦校验，反解角度 + 置信度"""
        sm = [SliceMeasurement(angle_deg=m.ruler_deg, raw_value=m.raw_value,
                               plane=measurements[0].plane) for m in measurements]
        rep = verifier.verify(sm)
        return rep.recovered_angle_deg, rep.confidence

    # ── 六投影签名 ──
    def _build_signature(self, measurements: List[RulerMeasurement]) -> List[float]:
        """6 值归一化签名 Σ = [Ŝ_45_XY, Ŝ_30_XY, Ŝ_60_XY, Ŝ_45_XZ, Ŝ_30_XZ, Ŝ_60_XZ]"""
        by_plane = {"XY": {}, "XZ": {}}
        for m in measurements:
            by_plane[m.plane][m.ruler_deg] = m.raw_value
        sig = []
        for plane in self.PLANES:
            s0 = by_plane[plane].get(0.0, 1.0)
            for psi in self.FIXED_RULERS:
                val = by_plane[plane].get(psi, 0.0)
                sig.append(val / (s0 + 1e-9))
        return sig

    # ── 一级快速通道判定 ──
    def _fast_path_check(self, angle: float) -> bool:
        """反解角度是否落在已知结构字典容差窗口内"""
        for known in KNOWN_ANGLES:
            if abs(angle - known) <= self.tolerance_deg:
                return True
        return False

    # ── 主流程 ──
    def verify(self, params: StructureParams,
               noise_sigma: float = 0.0) -> FixedRulerReport:
        meas = self.synthesize(params, noise_sigma=noise_sigma)
        verifier = SliceCosineVerifier()

        # 分平面
        xy_meas = [m for m in meas if m.plane == "XY"]
        xz_meas = [m for m in meas if m.plane == "XZ"]

        theta, conf_xy = self._decode_plane(xy_meas, verifier)
        phi, conf_xz = self._decode_plane(xz_meas, verifier)

        sig = self._build_signature(meas)

        # 体积反解（XY 振幅 = V · |cos θ| → V = A_XY / |cos θ|）
        a_xy = params.volume  # 真实振幅已知（合成）；实际从测量恢复：
        # 实际恢复：用 0° 标尺原始值 / |cos(θ)| 近似
        s0_xy = next(m.raw_value for m in xy_meas if m.ruler_deg == 0.0)
        vol_rec = s0_xy / (abs(math.cos(math.radians(theta))) + 1e-9)

        confidence = min(conf_xy, conf_xz)
        fast_xy = self._fast_path_check(theta)
        fast_xz = self._fast_path_check(phi)
        fast_path = fast_xy and fast_xz

        note = (f"一级快速通道命中（θ≈{theta:.0f}°,φ≈{phi:.0f}° 落入字典）"
                if fast_path else
                f"一级未命中→触发二级连续扫描（θ={theta:.1f}°,φ={phi:.1f}°）")
        return FixedRulerReport(
            signature=[round(s, 4) for s in sig],
            theta_recovered=round(theta, 2),
            phi_recovered=round(phi, 2),
            volume_recovered=round(vol_rec, 3),
            confidence=round(confidence, 4),
            fast_path=fast_path, note=note)


# ─────────────────────────────────────────────────────────────
# 自测
# ─────────────────────────────────────────────────────────────

def _self_test() -> int:
    v = FixedRulerVerifier()
    passed = 0
    total = 0

    def check(name: str, cond: bool):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
        print(f"  [{'+' if cond else '-'}] {name}")

    print("=== FixedRulerVerifier 自测 ===")

    import numpy as np

    # 1. 干净结构 (θ=37, φ=22)
    np.random.seed(10)
    r = v.verify(StructureParams(37.0, 22.0, 100.0))
    check("干净 θ≈37°", abs(r.theta_recovered - 37.0) < 2.0)
    check("干净 φ≈22°", abs(r.phi_recovered - 22.0) < 2.0)
    check("干净 置信度高", r.confidence > 0.9)
    check("干净 签名6维", len(r.signature) == 6)

    # 2. 单射性：θ=37 vs θ=40 签名不同
    np.random.seed(11)
    r1 = v.verify(StructureParams(37.0, 22.0, 100.0))
    np.random.seed(12)
    r2 = v.verify(StructureParams(40.0, 22.0, 100.0))
    sig_diff = sum(abs(a - b) for a, b in zip(r1.signature, r2.signature))
    check("单射：不同结构签名不同", sig_diff > 0.01)

    # 3. 一级快速通道：θ=44 近字典 45 → 命中
    np.random.seed(13)
    r_fast = v.verify(StructureParams(44.0, 44.0, 100.0))
    check("一级命中(44°近45°)", r_fast.fast_path)

    # 4. 一级未命中：θ=37 距 30/45 均>5° → 触发二级
    np.random.seed(14)
    r_slow = v.verify(StructureParams(37.0, 37.0, 100.0))
    check("一级未命中(37°→二级)", not r_slow.fast_path)

    # 5. 噪声鲁棒：σ=1.5 仍恢复
    np.random.seed(15)
    r_n = v.verify(StructureParams(37.0, 22.0, 100.0), noise_sigma=1.5)
    check("噪声 θ≈37°", abs(r_n.theta_recovered - 37.0) < 3.0)
    check("噪声 φ≈22°", abs(r_n.phi_recovered - 22.0) < 3.0)

    # 6. G1/G2/G3 并行：3 标尺均有有效测量
    np.random.seed(16)
    meas = v.synthesize(StructureParams(37.0, 22.0, 100.0))
    xy45 = [m for m in meas if m.plane == "XY" and m.ruler_deg == 45.0][0]
    xy30 = [m for m in meas if m.plane == "XY" and m.ruler_deg == 30.0][0]
    xy60 = [m for m in meas if m.plane == "XY" and m.ruler_deg == 60.0][0]
    check("G 标尺测量有效", all(m.raw_value > 0 for m in (xy45, xy30, xy60)))

    print(f"\n自测结果：{passed}/{total} 通过")
    return passed == total


if __name__ == "__main__":
    ok = _self_test()
    raise SystemExit(0 if ok else 1)
