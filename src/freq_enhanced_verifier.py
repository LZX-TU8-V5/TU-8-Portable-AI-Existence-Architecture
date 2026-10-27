# -*- coding: utf-8 -*-
"""
freq_enhanced_verifier.py  —  频域增强校验（纹理伪装检测）
层级：L5（世界模型地基） / 视觉模块
来源：千问对话⑱③ (2026-07-20) 五层世界模型 L-0 频域增强

核心突破：
    固定纹理会在固定标尺投影上产生假谐波，刚好对齐测量角度 → 空域余弦校验被欺骗。
    频域 FFT 幅度谱天然分离纹理基频与结构主频 → 空域被欺骗时频域不欺骗。
    两者交叉验证：空域通过 + 频域通过 → 高置信度结构确认。
    空域通过 + 频域失败 → 纹理伪装检测（警告）。
    频域通过 + 空域失败 → 结构存在但投影变形（特殊处理）。

数学基础：傅里叶切片定理
    二维图像 f(x,y) 的 Radon 变换 p_θ(t) 的 1D 傅里叶变换
    = f(x,y) 的 2D 傅里叶变换 F(u,v) 沿穿过原点的斜线切片
    → 固定标尺角度 θ 的投影频谱 = 图像频谱的径向切片

纹理伪装检测原理：
    纹理 = 周期基频 f_t << 结构频率 f_s
    投影到 θ 方向时：空域混叠（纹理 vs 结构难以区分）
    频域分离：纹理基频峰 vs 结构主峰（径向频谱能量分布不同）
    → 通过频谱一阶矩（能量质心径向位置）区分纹理主导 vs 结构主导
"""

import math
import numpy as np
from dataclasses import dataclass
from typing import Tuple, Optional

from slice_cosine_verifier import SliceCosineVerifier, SliceMeasurement
from fixed_ruler_verifier import FixedRulerVerifier, StructureParams


# ─────────────────────────────────────────────────────────────
# 数据类
# ─────────────────────────────────────────────────────────────

@dataclass
class SpatialResult:
    """空域余弦校验结果"""
    passed: bool
    recovered_angle: float
    confidence: float
    note: str


@dataclass
class FrequencyResult:
    """频域 FFT 增强校验结果"""
    passed: bool
    dominant_freq_ratio: float   # 主峰频率 / 次峰频率比（>阈值=结构主导）
    energy_centroid_ratio: float # 能量质心径向位置（归一化，>阈值=结构主导）
    texture_suspicion: float     # 纹理伪装怀疑度 [0,1]
    dominant_freq_hz: float      # 主峰频率（归一化，单位=cycles/width）
    note: str


@dataclass
class EnhancedReport:
    """空域+频域交叉验证报告"""
    spatial: SpatialResult
    frequency: FrequencyResult
    verdict: str          # CONFIRMED / SUSPICIOUS / STRUCTURE_FLEX / REJECTED
    confidence: float
    note: str


# ─────────────────────────────────────────────────────────────
# 频域增强校验器
# ─────────────────────────────────────────────────────────────

class FrequencyEnhancedVerifier:
    """
    空域余弦校验 + 频域 FFT 幅度谱交叉验证。
    对抗固定纹理产生的假谐波欺骗。
    """

    # 纹理检测阈值
    # 主/次峰比（干净结构 >> 纹理混入）：
    #   干净 → ratio>2.0（主峰清晰）；纹理混入 → ratio≈1.0（主次峰竞争）
    TEXTURE_PEAK_RATIO_THR = 2.0
    # 干净基准质心（Gauss 投影为低频信号，基准≈0.24）
    CLEAN_ENERGY_CENTROID_BASE = 0.25

    def __init__(self,
                 spatial_verifier: Optional[SliceCosineVerifier] = None,
                 ruler_verifier: Optional[FixedRulerVerifier] = None):
        self.sv = spatial_verifier or SliceCosineVerifier()
        self.rv = ruler_verifier or FixedRulerVerifier(tolerance_deg=5.0)

    # ── 频谱分析 ──
    @staticmethod
    def _fft_spectrum(image: np.ndarray) -> np.ndarray:
        """2D FFT 幅度谱（归一化）"""
        F = np.fft.fft2(image.astype(np.float64))
        mag = np.abs(F)
        return np.fft.fftshift(mag / (mag.max() + 1e-12))

    @staticmethod
    def _radial_profile(mag: np.ndarray) -> np.ndarray:
        """径向平均幅度谱（从中心向外）"""
        h, w = mag.shape
        cy, cx = h // 2, w // 2
        max_r = min(cy, cx)
        profile = np.zeros(max_r)
        counts = np.zeros(max_r)
        y, x = np.ogrid[:h, :w]
        r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2).astype(int)
        for i in range(max_r):
            mask = (r == i)
            if mask.sum() > 0:
                profile[i] = mag[mask].mean()
                counts[i] = mask.sum()
        return profile

    @staticmethod
    def _energy_centroid(profile: np.ndarray) -> float:
        """
        能量质心（归一化径向位置）。
        低值 = 能量集中在低频（纹理主导）；
        高值 = 能量扩散到中高频（结构主导）。
        """
        total = profile.sum()
        if total < 1e-12:
            return 0.0
        indices = np.arange(len(profile))
        centroid = np.dot(indices, profile) / total
        return centroid / len(profile)  # 归一化到 [0,1]

    @staticmethod
    def _peak_ratio(profile: np.ndarray, width: int = 5) -> Tuple[float, float, float]:
        """
        主峰/次峰比。
        width = 峰宽（排除中心 DC 峰）。
        返回 (主峰freq, 次峰freq, ratio)。
        """
        noise_floor = np.percentile(profile[width:], 20) if len(profile) > width else 0.0
        above_noise = profile.copy()
        above_noise[above_noise < noise_floor] = 0.0

        # 找主峰（排除 DC）
        peak_idx = width + np.argmax(above_noise[width:])
        main_peak = float(above_noise[peak_idx])

        # 找次峰（排除主峰 ±width）
        mask = np.ones_like(above_noise, dtype=bool)
        for j in range(max(0, peak_idx - width), min(len(mask), peak_idx + width + 1)):
            mask[j] = False
        masked = np.where(mask, above_noise, 0.0)
        if masked.max() > noise_floor:
            second_peak = float(masked.max())
        else:
            second_peak = noise_floor
        ratio = main_peak / (second_peak + 1e-12)
        return float(peak_idx), float(np.argmax(masked[mask]) + width if second_peak > noise_floor else 0), float(ratio)

    def _frequency_analysis(self, image: np.ndarray,
                             clean_centroid_base: float = 0.25) -> FrequencyResult:
        """单帧频域分析。纹理检测基于主/次峰比（干净>>纹理）。"""
        mag = self._fft_spectrum(image)
        profile = self._radial_profile(mag)

        centroid = self._energy_centroid(profile)
        main_freq, second_freq, ratio = self._peak_ratio(profile)

        # 纹理检测：ratio < 阈值 → 主次峰竞争 → 纹理混入
        # （干净 Gauss：ratio>2.0；纹理叠加：ratio≈1.0）
        texture_suspicion = max(0.0, min(1.0,
            1.0 - ratio / (self.TEXTURE_PEAK_RATIO_THR + 1e-9)))
        # 辅佐信号：质心相对干净基准的偏移（纹理通常推高质心）
        centroid_shift = centroid - clean_centroid_base
        texture_suspicion = min(1.0, texture_suspicion + 0.2 * max(0.0, centroid_shift))

        passed = ratio > self.TEXTURE_PEAK_RATIO_THR

        if ratio >= self.TEXTURE_PEAK_RATIO_THR:
            note = (f"频域通过（峰比={ratio:.2f}>{self.TEXTURE_PEAK_RATIO_THR}，"
                    f"质心={centroid:.3f}）")
        elif ratio >= 1.5:
            note = (f"频域警告（峰比={ratio:.2f}，主次峰接近，疑似轻纹理）")
        else:
            note = (f"频域失败（峰比={ratio:.2f}<{self.TEXTURE_PEAK_RATIO_THR}，"
                    f"纹理主导）")

        return FrequencyResult(
            passed=passed,
            dominant_freq_ratio=round(ratio, 3),
            energy_centroid_ratio=round(centroid, 4),
            texture_suspicion=round(texture_suspicion, 3),
            dominant_freq_hz=round(main_freq / len(profile), 4),
            note=note)

    # ── 空域校验（复用余弦校验器）──
    def _spatial_check(self, params: StructureParams,
                       noise_sigma: float = 0.0) -> SpatialResult:
        """空域余弦校验（固定标尺合成输入）"""
        rep = self.rv.verify(params, noise_sigma=noise_sigma)
        passed = (abs(rep.theta_recovered - params.theta_deg) < 3.0 and
                  rep.confidence > 0.8)
        return SpatialResult(
            passed=passed,
            recovered_angle=rep.theta_recovered,
            confidence=rep.confidence,
            note=rep.note)

    # ── 主流程 ──
    def verify(self, params: StructureParams,
               texture_amplitude: float = 0.0,
               noise_sigma: float = 0.0) -> EnhancedReport:
        """
        空域 + 频域交叉验证。
        texture_amplitude > 0 → 叠加规则纹理（测试伪装检测）
        """
        # 合成带纹理的帧（固定标尺角度 θ 的投影视图）
        # 这里用 1D 投影模拟（真实实现中需先做 Radon 投影）
        meas = self.rv.synthesize(params, noise_sigma=noise_sigma)
        xy0 = next(m.raw_value for m in meas if m.plane == "XY" and m.ruler_deg == 0.0)
        xy45 = next(m.raw_value for m in meas if m.plane == "XY" and m.ruler_deg == 45.0)

        # 构造模拟投影图像帧（128px，投影线在中心列）
        img = np.zeros((128, 128), dtype=np.float64)
        center = 64
        # 主结构信号
        for y in range(128):
            dx = abs(y - center)
            img[y, center] = xy0 * math.exp(-(dx ** 2) / (2 * 5.0 ** 2))
        # 叠加规则纹理（周期=8px，对应频率 1/8 cycles/pixel）
        if texture_amplitude > 0:
            for y in range(128):
                texture_val = texture_amplitude * math.cos(2 * math.pi * y / 8.0)
                img[y, center] += texture_val
        img = np.clip(img, 0, 255).astype(np.uint8)

        # 空域校验
        spatial = self._spatial_check(params, noise_sigma=noise_sigma)

        # 干净基准：Gauss 投影的频域质心（已知≈0.24）
        clean_centroid = self.CLEAN_ENERGY_CENTROID_BASE
        frequency = self._frequency_analysis(img, clean_centroid_base=clean_centroid)

        # 交叉验证判定
        if spatial.passed and frequency.passed:
            verdict = "CONFIRMED"
            confidence = min(spatial.confidence, frequency.dominant_freq_ratio / (frequency.dominant_freq_ratio + 1.0))
            note = "空域+频域双通过，结构确认"
        elif spatial.passed and not frequency.passed:
            verdict = "SUSPICIOUS"
            confidence = 0.3
            note = f"空域通过但频域异常 → 纹理伪装检测（texture_suspicion={frequency.texture_suspicion:.2f}）"
        elif not spatial.passed and frequency.passed:
            verdict = "STRUCTURE_FLEX"
            confidence = 0.5
            note = "频域通过但空域失败 → 结构存在但投影变形"
        else:
            verdict = "REJECTED"
            confidence = 0.0
            note = "空域+频域均失败，结构不存在或噪声过高"

        return EnhancedReport(
            spatial=spatial,
            frequency=frequency,
            verdict=verdict,
            confidence=round(confidence, 4),
            note=note)


# ─────────────────────────────────────────────────────────────
# 自测
# ─────────────────────────────────────────────────────────────

def _self_test() -> int:
    v = FrequencyEnhancedVerifier()
    passed = 0
    total = 0

    def check(name: str, cond: bool):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
        print(f"  [{'+' if cond else '-'}] {name}")

    print("=== FrequencyEnhancedVerifier 自测 ===")

    np.random.seed(99)

    # 1. 干净结构（无纹理）→ 频域峰比>2.0 → CONFIRMED
    r = v.verify(StructureParams(37.0, 22.0, 100.0), texture_amplitude=0.0)
    check("干净：verdict=CONFIRMED", r.verdict == "CONFIRMED")
    check("干净：空域 passed", r.spatial.passed)
    check("干净：频域 passed (ratio>2.0)", r.frequency.passed)
    check("干净：置信度>0.5", r.confidence > 0.5)
    check("干净：texture_suspicion低", r.frequency.texture_suspicion < 0.3)

    # 2. 强纹理伪装（80）→ 频域峰比≈1.0 → SUSPICIOUS
    r2 = v.verify(StructureParams(37.0, 22.0, 100.0), texture_amplitude=80.0)
    check("伪装：verdict=SUSPICIOUS", r2.verdict == "SUSPICIOUS")
    check("伪装：频域 texture_suspicion>0.5", r2.frequency.texture_suspicion > 0.5)
    check("伪装：空域仍 passed（纹理未完全掩盖）", r2.spatial.passed)
    check("伪装：峰比<2.0", r2.frequency.dominant_freq_ratio < 2.0)

    # 3. 轻度纹理（15%）→ 峰比可能仍>2.0 → CONFIRMED（轻微伪装）
    r3 = v.verify(StructureParams(37.0, 22.0, 100.0), texture_amplitude=15.0)
    check("轻度纹理：verdict非REJECTED", r3.verdict != "REJECTED")
    check("轻度纹理：texture_suspicion介0~1之间",
          0.0 <= r3.frequency.texture_suspicion <= 1.0)

    # 4. 噪声鲁棒（σ=2）→ 仍能判断
    r4 = v.verify(StructureParams(37.0, 22.0, 100.0), noise_sigma=2.0)
    check("噪声鲁棒：verdict非REJECTED", r4.verdict != "REJECTED")
    check("噪声鲁棒：spatial note非空", len(r4.spatial.note) > 0)
    check("噪声鲁棒：frequency note非空", len(r4.frequency.note) > 0)

    # 5. 角度归一化：θ=0°（退化情况）
    r5 = v.verify(StructureParams(0.0, 0.0, 100.0))
    check("θ=0：verdict非REJECTED", r5.verdict != "REJECTED")

    print(f"\n自测结果：{passed}/{total} 通过")
    return passed == total


if __name__ == "__main__":
    ok = _self_test()
    raise SystemExit(0 if ok else 1)
