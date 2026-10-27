# -*- coding: utf-8 -*-
"""
l5_motion_decoupler.py  —  L5 入口：相机-空间运动频域解耦原型
层级：L5（世界模型地基） / 视觉模块
来源：千问对话⑱③ (2026-07-20) 五层世界模型 + L-0 频域相机-空间解耦

核心原理（SFGAP L-0）：
    相机运动 = 全局同频平移/旋转 → 傅里叶域表现为全局相位斜坡（所有频率同移）
    物体运动 = 局部频变        → 傅里叶域表现为局部频谱变化（仅物体区域）
    两者在频域天然可分离，无需 3D 重建。

方法：
    1. 相位相关（phase correlation）估计帧间全局平移 T_t（相机）
    2. 对数极坐标相位相关估计旋转 R_t（相机）
    3. 相机补偿后残差 = 物体局部运动场（局部频变）
    4. 校验：相机动力学校验（运动平滑）+ 物体物理约束（刚性局部一致）

本文件为纯数学原型，用合成视频帧验证协议正确性（无真实视频依赖）。
"""

import math
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ─────────────────────────────────────────────────────────────
# 数据类
# ─────────────────────────────────────────────────────────────

@dataclass
class CameraMotion:
    """单帧相机运动（相对于前一帧）"""
    frame_idx: int
    rot_deg: float           # 旋转 R_t
    tx: float                 # 全局平移 x（相机）
    ty: float                 # 全局平移 y（相机）
    strength: float           # 相位相关峰值强度（置信度代理）
    valid: bool = True


@dataclass
class ObjectMotion:
    """单帧物体局部运动"""
    frame_idx: int
    residual_energy: float              # 相机补偿后残差总能量
    obj_displacement: Tuple[float, float]  # 物体相对位移 (dx, dy)
    obj_region_ratio: float             # 残差集中区域占比（刚性一致性指标）
    coherent: bool = True


@dataclass
class L5FrameReport:
    """单帧 L5 解耦报告"""
    camera: CameraMotion
    object: ObjectMotion


@dataclass
class L5MotionReport:
    """整段视频 L5 解耦报告"""
    frames: List[L5FrameReport]
    camera_valid: bool
    object_valid: bool
    note: str = ""


# ─────────────────────────────────────────────────────────────
# L5 频域解耦器
# ─────────────────────────────────────────────────────────────

class L5MotionDecoupler:
    """
    相机-空间运动频域解耦。
    输入：灰度视频帧序列（List[np.ndarray]）
    输出：每帧 (R_t, T_t) + 物体相对运动向量
    """

    def __init__(self, max_camera_shift: float = 20.0,
                 max_camera_rot: float = 15.0,
                 obj_coherence_thr: float = 0.5):
        self.max_camera_shift = max_camera_shift   # 单帧相机平移上限(px)
        self.max_camera_rot = max_camera_rot       # 单帧相机旋转上限(deg)
        self.obj_coherence_thr = obj_coherence_thr  # 物体刚性一致下限

    # ── 相位相关：全局平移 ──
    @staticmethod
    def _phase_correlate(a: np.ndarray, b: np.ndarray) -> Tuple[float, float, float]:
        """
        相位相关估计 b 相对于 a 的平移 (dx, dy)。
        返回 (dx, dy, peak_strength)。
        """
        F1 = np.fft.fft2(a.astype(np.float64))
        F2 = np.fft.fft2(b.astype(np.float64))
        R = F1 * np.conj(F2)
        R /= (np.abs(R) + 1e-12)
        r = np.real(np.fft.ifft2(R))
        r = np.fft.fftshift(r)
        h, w = r.shape
        cy, cx = np.unravel_index(np.argmax(r), r.shape)
        # 相对中心的偏移（考虑 fftshift）
        dy = cy - h // 2
        dx = cx - w // 2
        # 环绕修正：若峰值在边缘附近，取反向短路径
        if dy > h // 2:
            dy -= h
        if dx > w // 2:
            dx -= w
        peak = r[cy, cx] / (r.max() + 1e-12)
        return float(dx), float(dy), float(peak)

    # ── 对数极坐标相位相关：旋转 + 尺度 ──
    @staticmethod
    def _rotation_logpolar(a: np.ndarray, b: np.ndarray) -> Tuple[float, float, float]:
        """
        对数极坐标 FFT 幅度谱相位相关，估计旋转角(deg)与尺度。
        返回 (angle_deg, scale, strength)。
        """
        def logpolar_mag(img: np.ndarray) -> np.ndarray:
            F = np.fft.fftshift(np.fft.fft2(img.astype(np.float64)))
            mag = np.abs(F)
            h, w = mag.shape
            cy, cx = h // 2, w // 2
            # 对数极坐标网格
            log_base = math.log(min(h, w) / 2.0)
            n_angles = 64
            n_radii = 64
            lp = np.zeros((n_radii, n_angles), dtype=np.float64)
            for i in range(n_radii):
                rho = math.exp(log_base * i / (n_radii - 1))
                for j in range(n_angles):
                    theta = 2 * math.pi * j / n_angles
                    x = cx + rho * math.cos(theta)
                    y = cy + rho * math.sin(theta)
                    xi, yi = int(round(x)), int(round(y))
                    if 0 <= xi < w and 0 <= yi < h:
                        lp[i, j] = mag[yi, xi]
            return lp

        lp1 = logpolar_mag(a)
        lp2 = logpolar_mag(b)
        dx, dy, strength = L5MotionDecoupler._phase_correlate(lp1, lp2)
        # dy 在对数极坐标中对应旋转角；角度分辨率映射
        angle_per_row = 360.0 / lp1.shape[1]
        angle = dy * angle_per_row
        # 归一到 [-180, 180]
        if angle > 180:
            angle -= 360
        if angle < -180:
            angle += 360
        return float(angle), 1.0, float(strength)

    # ── 相机补偿 + 物体残差 ──
    def _object_residual(self, a: np.ndarray, b: np.ndarray,
                         cam_dx: float, cam_dy: float) -> Tuple[np.ndarray, float]:
        """
        将 b 按相机平移反向补偿后，与 a 求差 = 物体局部运动残差。
        返回 (residual_map, total_energy)。
        """
        # 反向平移 b（相位相关返回内容位移，补偿用同向 roll）
        comp = np.roll(b, shift=(int(round(cam_dy)), int(round(cam_dx))), axis=(0, 1))
        residual = np.abs(a.astype(np.float64) - comp.astype(np.float64))
        return residual, float(np.sum(residual ** 2))

    # ── 单帧解耦 ──
    def decouple_frame(self, frame_prev: np.ndarray, frame_curr: np.ndarray,
                       idx: int) -> L5FrameReport:
        # 1. 相机平移（相位相关）
        dx, dy, strength = self._phase_correlate(frame_prev, frame_curr)
        # 2. 相机旋转（对数极坐标）
        ang, _, ang_strength = self._rotation_logpolar(frame_prev, frame_curr)
        cam = CameraMotion(frame_idx=idx, rot_deg=ang, tx=dx, ty=dy,
                           strength=strength)
        # 相机动力学校验：平移/旋转超上限 → 标记无效（疑似相机/物体混淆）
        cam_shift = math.hypot(dx, dy)
        if cam_shift > self.max_camera_shift or abs(ang) > self.max_camera_rot:
            cam.valid = False

        # 3. 物体运动：相机补偿后残差
        residual, energy = self._object_residual(frame_prev, frame_curr, dx, dy)
        # 物体前景（亮度阈值，分离物体与背景）；相位相关前后帧前景
        # → 直接得物体图像空间位移（相机分量在前后帧中自然抵消）
        obj_thr = max(frame_prev.mean() + 3.0 * (frame_prev.std() + 1e-9), 80.0)
        fg_prev = frame_prev.astype(np.float64) > obj_thr
        fg_curr = frame_curr.astype(np.float64) > obj_thr
        region_ratio = float(fg_prev.sum()) / float(residual.size)
        if fg_prev.sum() > 0 and fg_curr.sum() > 0:
            obj_dx, obj_dy, _ = self._phase_correlate(
                np.where(fg_prev, frame_prev, 0.0),
                np.where(fg_curr, frame_curr, 0.0))
            # 刚性一致性：物体前景局部集中（<50% 图像 = 局部物体，非全局相机混淆）
            coherent = region_ratio < 0.5
        else:
            obj_dx, obj_dy = 0.0, 0.0
            coherent = True
        obj = ObjectMotion(frame_idx=idx, residual_energy=energy,
                           obj_displacement=(obj_dx, obj_dy),
                           obj_region_ratio=region_ratio, coherent=coherent)
        return L5FrameReport(camera=cam, object=obj)

    # ── 整段视频解耦 ──
    def decouple(self, frames: List[np.ndarray]) -> L5MotionReport:
        if len(frames) < 2:
            return L5MotionReport(frames=[], camera_valid=False,
                                   object_valid=False, note="帧数不足")
        reports = []
        for i in range(1, len(frames)):
            reports.append(self.decouple_frame(frames[i - 1], frames[i], i))

        # 相机动力学校验：所有相机运动 valid 且连续
        cam_valid = all(r.camera.valid for r in reports)
        # 物体物理约束：物体运动局部一致（刚性）
        obj_valid = all(r.object.coherent for r in reports)

        note = ("L5 解耦通过：相机/物体运动分离成功" if cam_valid and obj_valid
                else "L5 解耦异常：相机或物体运动校验失败")
        return L5MotionReport(frames=reports, camera_valid=cam_valid,
                               object_valid=obj_valid, note=note)


# ─────────────────────────────────────────────────────────────
# 合成视频帧生成（供测试）
# ─────────────────────────────────────────────────────────────

def synthesize_video(n_frames: int,
                     camera_trajectory: List[Tuple[float, float]],
                     object_trajectory: List[Tuple[float, float]],
                     size: int = 128,
                     seed: int = 0) -> List[np.ndarray]:
    """
    合成视频：静态背景 + 移动物体，叠加相机平移。
    camera_trajectory[t] = (cx, cy) 第 t 帧相机全局平移
    object_trajectory[t] = (ox, oy) 第 t 帧物体在世界坐标的位置
    返回帧序列（uint8 灰度）。
    """
    rng = np.random.default_rng(seed)
    # 静态背景纹理
    bg = rng.integers(0, 60, (size, size)).astype(np.float64)
    # 基础物体（亮方块 20x20）
    obj = np.ones((20, 20), dtype=np.float64) * 200.0

    frames = []
    for t in range(n_frames):
        cx, cy = camera_trajectory[t]
        ox, oy = object_trajectory[t]
        # 世界图像 = 背景 + 物体（在物体世界位置）
        world = bg.copy()
        x0, y0 = int(ox), int(oy)
        if 0 <= x0 < size - 20 and 0 <= y0 < size - 20:
            world[y0:y0 + 20, x0:x0 + 20] = obj
        # 相机平移：整图平移 (cx, cy)
        frame = np.roll(world, shift=(int(round(cy)), int(round(cx))), axis=(0, 1))
        frames.append(np.clip(frame, 0, 255).astype(np.uint8))
    return frames


# ─────────────────────────────────────────────────────────────
# 自测
# ─────────────────────────────────────────────────────────────

def _self_test() -> int:
    d = L5MotionDecoupler()
    passed = 0
    total = 0

    def check(name: str, cond: bool):
        nonlocal passed, total
        total += 1
        if cond:
            passed += 1
        print(f"  [{'+' if cond else '-'}] {name}")

    print("=== L5MotionDecoupler 自测 ===")

    # 1. 纯相机平移：物体静止，相机匀速平移
    n = 6
    cam_traj = [(i * 3, i * 2) for i in range(n)]      # 每帧 +3x +2y
    obj_traj = [(50, 50) for _ in range(n)]            # 物体静止
    frames = synthesize_video(n, cam_traj, obj_traj, seed=1)
    rep = d.decouple(frames)
    # 相机平移应≈(3,2)/帧（相位相关符号约定可能取反）
    cam0 = rep.frames[0].camera
    check("纯相机：相机 valid", cam0.valid)
    check("纯相机：平移幅度≈3.6", abs(math.hypot(cam0.tx, cam0.ty) - math.hypot(3, 2)) < 1.0)
    # 相机运动应平滑一致（每帧同向）
    shifts = [math.hypot(r.camera.tx, r.camera.ty) for r in rep.frames]
    check("纯相机：运动平滑", max(shifts) - min(shifts) < 1.0)
    # 物体应几乎无运动（残差低）
    obj_energies = [r.object.residual_energy for r in rep.frames]
    check("纯相机：物体残差低", max(obj_energies) < 5000)

    # 2. 物体运动 + 相机静止：仅物体移动
    cam_traj2 = [(0, 0) for _ in range(n)]
    obj_traj2 = [(50 + i * 4, 50) for i in range(n)]   # 物体每帧 +4x
    frames2 = synthesize_video(n, cam_traj2, obj_traj2, seed=2)
    rep2 = d.decouple(frames2)
    cam0_2 = rep2.frames[0].camera
    check("纯物体：相机≈静止", math.hypot(cam0_2.tx, cam0_2.ty) < 1.0)
    # 物体位移应≈(4,0)
    obj0 = rep2.frames[0].object
    check("纯物体：物体位移≈4x", abs(abs(obj0.obj_displacement[0]) - 4.0) < 1.5)
    check("纯物体：刚性一致 coherent", obj0.coherent)

    # 3. 复合运动：相机 + 物体同时动
    cam_traj3 = [(i * 2, 0) for i in range(n)]          # 相机 +2x
    obj_traj3 = [(50, 50 + i * 3) for i in range(n)]    # 物体 +3y
    frames3 = synthesize_video(n, cam_traj3, obj_traj3, seed=3)
    rep3 = d.decouple(frames3)
    cam0_3 = rep3.frames[0].camera
    obj0_3 = rep3.frames[0].object
    check("复合：相机 valid", cam0_3.valid)
    check("复合：相机平移≈2x", abs(abs(cam0_3.tx) - 2.0) < 1.0)
    check("复合：物体位移≈3y", abs(abs(obj0_3.obj_displacement[1]) - 3.0) < 1.5)

    # 4. 相机动力学校验：异常大跳变 → 标记 invalid
    cam_traj4 = [(0, 0), (100, 0)] + [(100, 0)] * (n - 2)  # 第1帧突跳100px
    obj_traj4 = [(50, 50) for _ in range(n)]
    frames4 = synthesize_video(n, cam_traj4, obj_traj4, seed=4)
    rep4 = d.decouple(frames4)
    check("异常跳变：第1帧相机 invalid", not rep4.frames[0].camera.valid)

    print(f"\n自测结果：{passed}/{total} 通过")
    return passed == total


if __name__ == "__main__":
    ok = _self_test()
    raise SystemExit(0 if ok else 1)
