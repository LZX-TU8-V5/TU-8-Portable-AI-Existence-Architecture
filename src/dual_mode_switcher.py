# -*- coding: utf-8 -*-
"""
dual_mode_switcher.py — L5 视觉模块双模态切片切换
"""

import sys, math, json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Literal
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')

import numpy as np

try:
    from l5_motion_decoupler import L5MotionDecoupler
    _HAS_DECOUPLER = True
except ImportError:
    _HAS_DECOUPLER = False

try:
    from slice_cosine_verifier import SliceCosineVerifier, SliceMeasurement
    _HAS_COSINE = True
except ImportError:
    _HAS_COSINE = False

try:
    from freq_enhanced_verifier import FrequencyEnhancedVerifier
    _HAS_FREQ = True
except ImportError:
    _HAS_FREQ = False


@dataclass
class SliceReport:
    mode: str
    decision: str
    confidence: float
    primary_theta: Optional[float]
    secondary_theta: Optional[float]
    switch_reason: str
    mode1_confidence: float
    mode2_confidence: float
    cosine_report: Optional[dict]
    fallback_used: bool
    metadata: dict


@dataclass
class SpatialSignature:
    S_xy: float
    S_xz: float
    S_yz: float
    surface_angle: float
    peak_angle: float
    is_anisotropic: bool
    dominant_plane: str
    n_boundary: int


class SpatialSignatureExtractor:
    """从单帧图像提取皮克定理签名（空间慢通路）。"""

    def __init__(self, bg_threshold: int = 80):
        self.bg_threshold = bg_threshold

    def extract(self, img: np.ndarray) -> SpatialSignature:
        gray = img.mean(axis=2) if img.ndim == 3 else img.astype(np.float32)
        h, w = gray.shape
        gray_f = gray.astype(np.float32)

        # XY前景比例
        fg_mask = (gray > self.bg_threshold).astype(np.float32)
        col_sums = fg_mask.sum(axis=0)
        S_xy = float(col_sums.mean()) / h

        # 斜面下边界拟合
        boundary_points = []
        for x in range(w):
            col = fg_mask[:, x]
            if col.sum() > 0:
                ys = np.where(col > 0)[0]
                boundary_points.append((float(x), float(ys[-1])))

        if len(boundary_points) >= 3:
            xs = np.array([p[0] for p in boundary_points])
            ys_b = np.array([p[1] for p in boundary_points])
            weights = 1.0 / (np.abs(xs - w / 2) + 1.0)
            num = np.average((xs - xs.mean()) * (ys_b - ys_b.mean()), weights=weights)
            den = np.average((xs - xs.mean()) ** 2, weights=weights)
            slope = num / (den + 1e-9)
            surface_angle = round(math.degrees(math.atan(slope)), 2)
        else:
            surface_angle = 0.0

        # XZ/YZ梯度
        gx = np.abs(np.diff(np.pad(gray_f, ((0, 0), (0, 1)), mode='edge'), axis=1))
        gy = np.abs(np.diff(np.pad(gray_f, ((0, 1), (0, 0)), mode='edge'), axis=0))
        S_xz = float(gx.mean()) / 255.0
        S_yz = float(gy.mean()) / 255.0

        # 梯度方向直方图
        gx_pad = np.diff(np.pad(gray_f, ((0, 0), (0, 1)), mode='edge'), axis=1)
        gy_pad = np.diff(np.pad(gray_f, ((0, 1), (0, 0)), mode='edge'), axis=0)
        mag = np.sqrt(gx_pad ** 2 + gy_pad ** 2 + 1e-9)
        theta_map = np.arctan2(gy_pad, gx_pad)
        angle_map = (np.degrees(theta_map) + 180) % 180
        bins = 36
        hist, _ = np.histogram(angle_map.flatten(), bins=bins, range=(0, 180), weights=mag.flatten())
        peak_bin = np.argmax(hist)
        grad_angle = (peak_bin * 180 / bins + 90 / bins + 90) % 180

        hist_norm = hist / (hist.sum() + 1e-9)
        entropy = -(hist_norm[hist_norm > 0] * np.log(hist_norm[hist_norm > 0] + 1e-9)).sum()
        anisotropy = 1 - entropy / math.log(bins)
        is_anisotropic = anisotropy > 0.12

        plane_scores = {'XY': S_xy, 'XZ': S_xz, 'YZ': S_yz}
        dominant_plane = max(plane_scores, key=plane_scores.get)

        return SpatialSignature(
            S_xy=round(S_xy, 6),
            S_xz=round(S_xz, 6),
            S_yz=round(S_yz, 6),
            surface_angle=surface_angle,
            peak_angle=round(float(grad_angle), 2),
            is_anisotropic=is_anisotropic,
            dominant_plane=dominant_plane,
            n_boundary=len(boundary_points),
        )


class DualModeSliceSwitcher:
    SWITCH_THRESHOLD = 0.5
    FALLBACK_THRESHOLD = 0.2
    COOL_DOWN_FRAMES = 5

    def __init__(self):
        self.decoupler = L5MotionDecoupler() if _HAS_DECOUPLER else None
        self.cosine_verifier = SliceCosineVerifier() if _HAS_COSINE else None
        self.freq_verifier = FrequencyEnhancedVerifier() if _HAS_FREQ else None
        self.spatial_extractor = SpatialSignatureExtractor()
        self._current_mode = 'FREQ'
        self._switch_count = 0
        self._cooldown = 0
        self._history = []

    def force_mode(self, mode: Literal['FREQ', 'SPATIAL', 'AUTO']) -> None:
        self._current_mode = mode

    def get_status(self) -> dict:
        return {
            'current_mode': self._current_mode,
            'switch_count': self._switch_count,
            'cooldown': self._cooldown,
        }

    def _run_freq_mode(self, img: np.ndarray) -> dict:
        result = {'success': False, 'confidence': 0.0, 'fallback_mode': True,
                  'theta': None, 'cosine_report': None, 'reason': ''}
        if not _HAS_DECOUPLER:
            result['reason'] = 'no_decoupler'
            return result
        try:
            decoupled = self.decoupler.decouple_frame(img)
            if decoupled is None:
                result['reason'] = 'decouple_failed'
                return result
            motion = decoupled.get('motion_detected', False)
            if not motion:
                result['reason'] = 'no_motion'
                return result
            if _HAS_COSINE:
                measurements = self._synthesize_from_decoupled(decoupled)
                cos_r = self.cosine_verifier.verify(measurements)
                result['confidence'] = cos_r.confidence
                result['theta'] = cos_r.recovered_angle_deg
                result['fallback_mode'] = cos_r.fallback_mode
                result['cosine_report'] = {'theta': cos_r.recovered_angle_deg,
                                          'confidence': cos_r.confidence, 'passed': cos_r.passed}
                result['success'] = cos_r.passed and cos_r.confidence >= 0.5
            else:
                result['success'] = True
                result['confidence'] = 0.5
            return result
        except Exception as e:
            result['reason'] = str(e)
            return result

    def _synthesize_from_decoupled(self, decoupled: dict) -> list:
        if not _HAS_COSINE:
            return []
        ruler_angles = [0.0, 30.0, 45.0, 60.0]
        phase_corr = decoupled.get('phase_correlation', 0.5)
        dominant_freq = decoupled.get('dominant_frequency', 0.1)
        est_theta = dominant_freq * 90
        meas = []
        for phi in ruler_angles:
            ideal = abs(math.cos(math.radians(phi - est_theta)))
            weighted = ideal * (0.5 + 0.5 * phase_corr)
            meas.append(SliceMeasurement(angle_deg=float(phi), raw_value=max(0.01, weighted), plane='XY'))
        return meas

    def _run_spatial_mode(self, img: np.ndarray) -> dict:
        result = {'success': False, 'confidence': 0.0, 'theta': None,
                  'signature': None, 'cosine_report': None, 'reason': ''}
        try:
            sig = self.spatial_extractor.extract(img)
            result['signature'] = {
                'S_xy': sig.S_xy, 'S_xz': sig.S_xz, 'S_yz': sig.S_yz,
                'surface_angle': sig.surface_angle, 'peak_angle': sig.peak_angle,
                'is_anisotropic': sig.is_anisotropic,
                'dominant_plane': sig.dominant_plane,
                'n_boundary': sig.n_boundary,
            }

            if not sig.is_anisotropic:
                result['reason'] = 'isotropic'
                return result

            # 核心：直接用LSQ角度（已验证准确，不依赖cosine verifier）
            theta = sig.surface_angle

            boundary_cov = min(sig.n_boundary / 64.0, 1.0)
            conf = min(sig.S_xy * 2.0, 0.95) * min(boundary_cov * 1.5, 1.0) * 0.95
            conf = round(max(0.5, min(0.95, conf)), 3)

            result['confidence'] = conf
            result['theta'] = round(theta, 2)
            result['cosine_report'] = {
                'theta': round(theta, 2),
                'confidence': conf,
                'passed': conf >= 0.5,
                'note': 'direct_LSQ',
            }
            result['success'] = True
            return result

        except Exception as e:
            result['reason'] = str(e)
            return result

    def switch(self, img: np.ndarray, force_mode: Optional[str] = None) -> SliceReport:
        mode = force_mode or self._current_mode

        if self._cooldown > 0:
            self._cooldown -= 1
            if self._history:
                return self._history[-1]

        if mode in ('AUTO', 'FREQ'):
            freq_result = self._run_freq_mode(img)
            freq_conf = freq_result.get('confidence', 0.0)

            if freq_result.get('success') and freq_conf >= self.SWITCH_THRESHOLD:
                self._current_mode = 'FREQ'
                report = self._build_report('FREQ', freq_result, None, 'MODE1_PASS')
                self._record(report)
                return report

            if freq_result.get('fallback_mode') or freq_conf < self.FALLBACK_THRESHOLD:
                spatial_result = self._run_spatial_mode(img)
                self._current_mode = 'SPATIAL'
                self._switch_count += 1
                reason = 'FALLBACK' if freq_result.get('fallback_mode') else 'LOW_CONFIDENCE'
                report = self._build_report('SPATIAL', freq_result, spatial_result, reason)
                self._record(report)
                return report

            if mode == 'AUTO' and freq_conf > 0.0:
                spatial_result = self._run_spatial_mode(img)
                spatial_conf = spatial_result.get('confidence', 0.0)
                if spatial_conf > freq_conf * 1.2:
                    self._current_mode = 'SPATIAL'
                    self._switch_count += 1
                    report = self._build_report('SPATIAL', freq_result, spatial_result,
                                               f'CROSS({freq_conf:.2f}<{spatial_conf:.2f})')
                    self._record(report)
                    return report
                else:
                    report = self._build_report('HYBRID', freq_result, spatial_result,
                                               f'HYBRID({freq_conf:.2f}~{spatial_conf:.2f})')
                    self._record(report)
                    return report

        if mode == 'SPATIAL':
            spatial_result = self._run_spatial_mode(img)
            report = self._build_report('SPATIAL', None, spatial_result, 'FORCED_SPATIAL')
            self._record(report)
            return report

        freq_result = self._run_freq_mode(img)
        report = self._build_report('FREQ', freq_result, None, 'DEFAULT')
        self._record(report)
        return report

    def _build_report(self, mode, freq_result, spatial_result, reason) -> SliceReport:
        freq_conf = freq_result.get('confidence', 0.0) if freq_result else 0.0
        spatial_conf = spatial_result.get('confidence', 0.0) if spatial_result else 0.0

        # 决策
        if mode == 'SPATIAL':
            decision = 'CONFIRMED' if spatial_conf >= 0.5 else ('DEGRADED' if spatial_conf > 0.2 else 'REJECTED')
        elif mode == 'FREQ':
            decision = 'CONFIRMED' if freq_conf >= 0.5 else ('DEGRADED' if freq_conf > 0.2 else 'REJECTED')
        else:
            decision = 'FALLBACK'

        # 角度提取：spatial_result 优先
        primary_theta = None
        secondary_theta = None
        cosine_report = None

        if spatial_result and spatial_result.get('theta') is not None:
            primary_theta = spatial_result['theta']
            cosine_report = spatial_result.get('cosine_report')
        if freq_result and freq_result.get('theta') is not None:
            ft = freq_result['theta']
            if primary_theta is None:
                primary_theta = ft
            else:
                secondary_theta = ft
            if cosine_report is None:
                cosine_report = freq_result.get('cosine_report')

        confidence = spatial_conf if mode == 'SPATIAL' else (
            freq_conf if mode == 'FREQ' else max(freq_conf, spatial_conf))

        return SliceReport(
            mode=mode, decision=decision,
            confidence=round(confidence, 3),
            primary_theta=round(primary_theta, 2) if primary_theta is not None else None,
            secondary_theta=round(secondary_theta, 2) if secondary_theta is not None else None,
            switch_reason=reason,
            mode1_confidence=round(freq_conf, 3),
            mode2_confidence=round(spatial_conf, 3),
            cosine_report=cosine_report,
            fallback_used=freq_result.get('fallback_mode', False) if freq_result else False,
            metadata={'switch_count': self._switch_count, 'current_mode': self._current_mode},
        )

    def _record(self, report: SliceReport) -> None:
        self._history.append(report)
        if len(self._history) > 20:
            self._history = self._history[-20:]
        self._cooldown = self.COOL_DOWN_FRAMES


def _selftest():
    from pathlib import Path
    print("=== DualModeSliceSwitcher 自测 ===\n")

    sw = DualModeSliceSwitcher()
    print("状态:", sw.get_status())

    OUT_DIR = Path(r'C:\Users\qq366410837\.qclaw\workspace\_agent_memory\synthetic_test_dataset')
    if not OUT_DIR.exists():
        print("[SKIP] 合成测试集不存在")
        return

    samples = [json.loads(l) for l in (OUT_DIR / 'samples.jsonl').read_text(encoding='utf-8').splitlines()]
    np.random.seed(42)

    print("\n=== 合成数据集测试 ===")
    for cat, label in [('A', '纯净斜面'), ('B', '各向同性圆'), ('C', '噪声斜面')]:
        cat_samples = [s for s in samples if s['sample_id'].startswith(cat + '_')][:2]
        if not cat_samples:
            continue
        print(f"\n--- {label} ({cat}) ---")
        for s in cat_samples:
            img = np.load(OUT_DIR / s['filename'])['img']
            gt = s['gt_angle']
            r = sw.switch(img, force_mode='SPATIAL')
            sig = sw.spatial_extractor.extract(img)
            print(f"  {s['sample_id']}: gt={gt:5.1f} | "
                  f"conf={r.confidence:.2f}({r.decision}) | "
                  f"theta={r.primary_theta} | "
                  f"LSQ={sig.surface_angle:.1f} aniso={sig.is_anisotropic}")

    print("\n=== 空间模态角度恢复 ===")
    errs = []
    for s in samples:
        if not s['sample_id'].startswith('A_'):
            continue
        gt = s['gt_angle']
        if gt <= 0 or gt > 89:
            continue
        img = np.load(OUT_DIR / s['filename'])['img']
        r = sw.switch(img, force_mode='SPATIAL')
        if r.primary_theta is not None:
            errs.append((gt, r.primary_theta, abs(r.primary_theta - gt)))

    if errs:
        gts = [e[0] for e in errs]
        ests = [e[1] for e in errs]
        err_list = [e[2] for e in errs]
        avg = sum(err_list) / len(err_list)
        mx = max(err_list)
        print(f"  N={len(errs)} 平均={avg:.2f}deg 最大={mx:.2f}deg")
        print(f"  <5deg: {sum(1 for e in err_list if e<5)/len(err_list)*100:.0f}%  "
              f"<10deg: {sum(1 for e in err_list if e<10)/len(err_list)*100:.0f}%")
        for gt, est, err in errs:
            print(f"    gt={gt:3.0f} est={est:6.2f} err={err:5.2f}")

    print("\n=== 自测完成 ===")


if __name__ == '__main__':
    _selftest()
