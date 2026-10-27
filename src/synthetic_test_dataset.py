"""
synthetic_test_dataset.py — L5 视觉模块测试集构建器

来源：视觉模块 L5 入口核心校验协议
目标：为 G0~G3 校验器、频域增强校验、双模态切片切换提供验证数据

测试集分类：
  A. 纯净斜面：各向异性，有明确取向
  B. 各向同性圆：无取向（应被余弦校验器拒绝）
  C. 噪声污染：σ∈{0.5%, 1%, 2%}
  D. 纹理覆盖：斜面被纹理"掩埋"
  E. 双斜面：场景含两个不同角度斜面
  F. 边界角度：0°, 5°, 90°（极限情况）
  G. 多物体：scene 含多个独立取向物体
"""

import json
import math
import numpy as np
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

WS = Path("C:/Users/qq366410837/.qclaw/workspace")
OUT_DIR = WS / "_agent_memory" / "synthetic_test_dataset"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# 皮克定理计算（Pick-based signature）
# ─────────────────────────────────────────────────────────────────────────────

def pick_theorem_signature(theta_deg: float, slab_w: int = 128, slab_h: int = 128) -> dict:
    """
    计算斜面（斜率 tan(θ)）的皮克定理签名。

    斜面：y = tan(θ)·x，左闭右开，x∈[0, W]
    皮克定理：I = A - B/2 - 1
    归一化：S = 2I / W² = (2A - B) / W²
    """
    theta = math.radians(theta_deg)
    t = abs(math.tan(theta))  # 斜率

    # 格子点计数
    interior = 0
    boundary = 0

    for i in range(slab_w):  # i = x 整数坐标
        y0 = t * i
        y1 = t * (i + 1)
        # 格子点 x=i, y=0..floor(y1)
        iy_max = int(math.floor(y1))
        iy_min = int(math.ceil(y0))
        interior += max(0, iy_max - iy_min + 1)

        # 边界点：y0 和 y1 与格子线的交点
        boundary += 1 if y0 == int(y0) else 0
        boundary += 1 if y1 == int(y1) else 0

    # 上边界（y=0 是基线，一般不计入）
    boundary += slab_w  # 底部边

    A = 0.5 * slab_w * t * slab_w  # 梯形面积
    I = interior
    B = boundary

    # Pick theorem: A = I + B/2 - 1
    # → I = A - B/2 + 1
    # 实际我们用格子计数 I 做签名
    S_norm = (2 * interior - boundary) / (slab_w ** 2)
    S_xy = S_norm
    S_xz = abs(math.cos(theta)) * S_xy  # XZ 切面投影
    S_yz = abs(math.sin(theta))  # YZ 切面（正交于斜面方向）

    return {
        "theta": theta_deg,
        "S_xy": round(S_xy, 6),
        "S_xz": round(S_xz, 6),
        "S_yz": round(S_yz, 6),
        "interior": interior,
        "boundary": boundary,
        "area": round(A, 4),
    }


def compute_gt_signatures(angles: list) -> dict:
    """批量计算 ground-truth 签名"""
    return {f"theta_{a}": pick_theorem_signature(a) for a in angles}


# ─────────────────────────────────────────────────────────────────────────────
# 图像合成器
# ─────────────────────────────────────────────────────────────────────────────

def make_slab_image(
    theta_deg: float,
    size: int = 128,
    noise_sigma: float = 0.0,
    texture_cover: float = 0.0,
    fill_color: tuple = (180, 160, 140),
) -> np.ndarray:
    """
    合成斜面图像。

    Args:
        theta_deg: 斜面角度
        noise_sigma: 高斯噪声标准差（像素，0=无噪声）
        texture_cover: 纹理覆盖比例（0~1）
        fill_color: 斜面填充色 (R,G,B)
    """
    img = np.full((size, size, 3), 40, dtype=np.uint8)  # 背景=深灰

    t = math.tan(math.radians(theta_deg))
    # 斜面 y = t * x，从 x=0 到 x=size-1
    # 斜面上方为斜面区域（填充色）

    for x in range(size):
        y_thresh = int(round(t * x))
        if 0 <= y_thresh < size:
            # 斜面区域：y < t*x（上方）
            img[:y_thresh+1, x] = fill_color

    # 高斯噪声
    if noise_sigma > 0:
        noise = np.random.normal(0, noise_sigma, (size, size, 3))
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    # 纹理覆盖：叠加高频噪声块
    if texture_cover > 0:
        n_blocks = int(texture_cover * 20)
        for _ in range(n_blocks):
            bx = np.random.randint(0, size - 8)
            by = np.random.randint(0, size - 8)
            bs = np.random.randint(4, 12)
            tex = np.random.randint(60, 200, (bs, bs, 3), dtype=np.uint8)
            img[by:by+bs, bx:bx+bs] = tex

    return img


def make_circle_image(
    radius_ratio: float = 0.4,
    size: int = 128,
    noise_sigma: float = 0.0,
    fill_color: tuple = (180, 160, 140),
) -> np.ndarray:
    """各向同性圆：无取向结构，应被余弦校验器拒绝"""
    img = np.full((size, size, 3), 40, dtype=np.uint8)
    cx, cy = size // 2, size // 2
    r = int(size * radius_ratio)

    yy, xx = np.ogrid[:size, :size]
    mask = (xx - cx)**2 + (yy - cy)**2 <= r**2
    img[mask] = fill_color

    if noise_sigma > 0:
        noise = np.random.normal(0, noise_sigma, (size, size, 3))
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return img


def make_dual_slab_image(
    theta1: float,
    theta2: float,
    size: int = 128,
    noise_sigma: float = 0.0,
) -> np.ndarray:
    """双斜面：含两个不同角度的斜面（scene 级测试）"""
    img = np.full((size, size, 3), 40, dtype=np.uint8)

    for theta, color in [(theta1, (180, 160, 140)), (theta2, (140, 160, 180))]:
        t = math.tan(math.radians(theta))
        for x in range(size):
            y_thresh = int(round(t * x))
            if 0 <= y_thresh < size:
                img[:y_thresh+1, x] = color

    if noise_sigma > 0:
        noise = np.random.normal(0, noise_sigma, (size, size, 3))
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return img


def make_multi_object_image(
    angles: list,
    size: int = 128,
    noise_sigma: float = 0.0,
) -> np.ndarray:
    """多物体 scene：每个物体独立取向"""
    img = np.full((size, size, 3), 40, dtype=np.uint8)

    n = len(angles)
    colors = [(180, 160, 140), (140, 180, 140), (140, 140, 180),
              (180, 140, 160), (160, 180, 140), (140, 160, 180)]

    for i, theta in enumerate(angles):
        # 每个物体占一个小块
        bx = (i % 3) * (size // 3) + 4
        by = (i // 3) * (size // 3) + 4
        bw = size // 3 - 8
        bh = size // 3 - 8

        t = math.tan(math.radians(theta))
        color = colors[i % len(colors)]
        block = img[by:by+bh, bx:bx+bw]
        for x in range(bw):
            y_thresh = int(round(t * x))
            if 0 <= y_thresh < bh:
                block[:y_thresh+1, x] = color

    if noise_sigma > 0:
        noise = np.random.normal(0, noise_sigma, (size, size, 3))
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    return img


# ─────────────────────────────────────────────────────────────────────────────
# 皮克签名计算（从图像，不依赖角度标签）
# ─────────────────────────────────────────────────────────────────────────────

def image_to_pick_signature(
    img: np.ndarray,
    axis: str = "xy",
    bg_threshold: int = 80,
) -> dict:
    """
    从图像提取皮克签名（无角度标签时的物理签名）。

    策略：
    - xy: 逐列计数斜面像素，y方向投影
    - xz: 模拟深度切片（沿x方向像素密度）
    - yz: 模拟侧向切片（沿y方向像素密度）

    axis:
      xy: 皮克面积（斜面上方像素数 / 总面积）
      xz: x方向梯度投影
      yz: y方向投影
    """
    gray = img.mean(axis=2) if img.ndim == 3 else img
    h, w = gray.shape

    if axis == "xy":
        # XY 切面：按 x 列计数斜面像素（像素值 > bg_threshold）
        slab_pixels_per_x = (gray > bg_threshold).sum(axis=0)  # shape (w,)
        # 主导切面 S_xy
        S_xy = slab_pixels_per_x.mean() / h  # 归一化面积比
        return {"S_xy": round(S_xy, 6), "raw": slab_pixels_per_x.tolist()}

    elif axis == "xz":
        # XZ 切面：x方向积分投影（模拟深度）
        proj = gray.mean(axis=0)  # shape (w,)
        S_xz = (proj - proj.min()) / (proj.max() - proj.min() + 1e-9)
        return {"S_xz": round(S_xz.mean(), 6), "raw": proj.tolist()}

    elif axis == "yz":
        proj = gray.mean(axis=1)  # shape (h,)
        S_yz = (proj - proj.min()) / (proj.max() - proj.min() + 1e-9)
        return {"S_yz": round(S_yz.mean(), 6), "raw": proj.tolist()}

    return {}


def extract_peak_angle(img: np.ndarray) -> float:
    """
    从图像提取主导方向角（°）。
    用 Sobel 梯度方向直方图。
    """
    gray = img.mean(axis=2) if img.ndim == 3 else img
    gray = gray.astype(np.float32)

    # Sobel 梯度
    gx = np.diff(np.pad(gray, ((0,0),(0,1)), mode='edge'), axis=1)
    gy = np.diff(np.pad(gray, ((0,1),(0,0)), mode='edge'), axis=0)

    mag = np.sqrt(gx**2 + gy**2)
    theta_map = np.arctan2(gy, gx + 1e-9)  # -π ~ π
    angle_map = np.degrees(theta_map) % 180  # 0~180（方向无符号）

    # 梯度方向直方图
    bins = 36
    hist, _ = np.histogram(angle_map.flatten(), bins=bins, range=(0, 180),
                           weights=mag.flatten())
    peak_bin = np.argmax(hist)
    peak_angle = peak_bin * 180 / bins + 90 / bins  # 取 bin 中心
    return round(peak_angle, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 主构建函数
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TestSample:
    sample_id: str
    scene_type: str
    gt_angle: float
    gt_angles: list
    filename: str
    metadata: dict


def build_dataset(
    noise_levels: list = [0.0, 0.5, 1.0, 2.0],
    texture_levels: list = [0.0, 0.2, 0.4],
    output_format: str = "numpy",
) -> dict:
    """
    构建完整测试集。

    输出结构：
      dataset/
        samples.jsonl   # 元数据
        signatures.json  # GT 签名
        raw/             # 原始图像（numpy .npz）
    """
    samples = []
    all_signatures = {}
    sample_idx = 0

    # ── A. 纯净斜面 ─────────────────────────────────────────────────────────
    angles_clean = [0, 5, 15, 30, 37, 45, 60, 75, 90]
    for theta in angles_clean:
        if theta == 0:
            # 水平面：皮克签名为 0
            img = np.full((128, 128, 3), 40, dtype=np.uint8)
        elif theta == 90:
            # 垂直面：全填充
            img = np.full((128, 128, 3), (180, 160, 140), dtype=np.uint8)
        else:
            img = make_slab_image(theta, size=128, noise_sigma=0.0)

        sample_idx += 1
        sid = f"A_{theta:03d}"
        fname = f"{sid}.npz"
        npz_path = OUT_DIR / fname
        np.savez_compressed(npz_path, img=img)

        sig = pick_theorem_signature(theta)
        all_signatures[sid] = sig

        samples.append(TestSample(
            sample_id=sid,
            scene_type="A_clean_slab",
            gt_angle=theta,
            gt_angles=[theta],
            filename=fname,
            metadata=sig,
        ))

    # ── B. 各向同性圆 ──────────────────────────────────────────────────────
    for noise in noise_levels:
        for radius in [0.3, 0.4, 0.5]:
            img = make_circle_image(radius_ratio=radius, size=128, noise_sigma=noise)
            sample_idx += 1
            sid = f"B_n{int(noise*10):02d}_r{int(radius*10):02d}"
            fname = f"{sid}.npz"
            np.savez_compressed(OUT_DIR / fname, img=img)

            samples.append(TestSample(
                sample_id=sid,
                scene_type="B_isotropic_circle",
                gt_angle=-1,  # 无取向
                gt_angles=[],
                filename=fname,
                metadata={"radius": radius, "noise_sigma": noise},
            ))

    # ── C. 噪声污染斜面 ─────────────────────────────────────────────────────
    for theta in [15, 37, 45, 60]:
        for noise in noise_levels:
            if noise == 0:
                continue
            img = make_slab_image(theta, size=128, noise_sigma=noise)
            sample_idx += 1
            sid = f"C_{theta:03d}_n{int(noise*10):02d}"
            fname = f"{sid}.npz"
            np.savez_compressed(OUT_DIR / fname, img=img)
            sig = pick_theorem_signature(theta)
            sig["noise_sigma"] = noise
            all_signatures[sid] = sig

            samples.append(TestSample(
                sample_id=sid,
                scene_type="C_noisy_slab",
                gt_angle=theta,
                gt_angles=[theta],
                filename=fname,
                metadata={"noise_sigma": noise, **sig},
            ))

    # ── D. 纹理覆盖斜面 ─────────────────────────────────────────────────────
    for theta in [37, 45]:
        for tex in texture_levels:
            if tex == 0:
                continue
            img = make_slab_image(theta, size=128, texture_cover=tex)
            sample_idx += 1
            sid = f"D_{theta:03d}_t{int(tex*10):02d}"
            fname = f"{sid}.npz"
            np.savez_compressed(OUT_DIR / fname, img=img)
            sig = pick_theorem_signature(theta)
            sig["texture_cover"] = tex
            all_signatures[sid] = sig

            samples.append(TestSample(
                sample_id=sid,
                scene_type="D_texture_covered",
                gt_angle=theta,
                gt_angles=[theta],
                filename=fname,
                metadata={"texture_cover": tex, **sig},
            ))

    # ── E. 双斜面 ──────────────────────────────────────────────────────────
    pairs = [(15, 60), (30, 75), (37, 45)]
    for theta1, theta2 in pairs:
        img = make_dual_slab_image(theta1, theta2, size=128)
        sample_idx += 1
        sid = f"E_{theta1:03d}_{theta2:03d}"
        fname = f"{sid}.npz"
        np.savez_compressed(OUT_DIR / fname, img=img)

        samples.append(TestSample(
            sample_id=sid,
            scene_type="E_dual_slab",
            gt_angle=-1,  # 两个角度
            gt_angles=[theta1, theta2],
            filename=fname,
            metadata={"theta1": theta1, "theta2": theta2},
        ))

    # ── F. 多物体 ──────────────────────────────────────────────────────────
    combos = [[15, 60], [30, 45, 75], [5, 37, 82]]
    for angles in combos:
        img = make_multi_object_image(angles, size=128)
        sample_idx += 1
        sid = f"G_{'-'.join(f'{a:03d}' for a in angles)}"
        fname = f"{sid}.npz"
        np.savez_compressed(OUT_DIR / fname, img=img)

        samples.append(TestSample(
            sample_id=sid,
            scene_type="F_multi_object",
            gt_angle=-1,
            gt_angles=angles,
            filename=fname,
            metadata={"angles": angles},
        ))

    # ── 写元数据 ────────────────────────────────────────────────────────────
    samples_path = OUT_DIR / "samples.jsonl"
    with open(samples_path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(asdict(s), ensure_ascii=False) + "\n")

    sigs_path = OUT_DIR / "signatures.json"
    with open(sigs_path, "w", encoding="utf-8") as f:
        json.dump(all_signatures, f, ensure_ascii=False, indent=2)

    # 统计
    type_counts = {}
    for s in samples:
        type_counts[s.scene_type] = type_counts.get(s.scene_type, 0) + 1

    summary = {
        "total_samples": len(samples),
        "type_counts": type_counts,
        "categories": {
            "A": "纯净斜面（边界角度）",
            "B": "各向同性圆（应拒绝）",
            "C": "噪声污染斜面",
            "D": "纹理覆盖斜面",
            "E": "双斜面（scene级）",
            "F": "多物体（scene级）",
        }
    }

    summary_path = OUT_DIR / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return {
        "samples": samples,
        "summary": summary,
        "out_dir": str(OUT_DIR),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 测试集验证
# ─────────────────────────────────────────────────────────────────────────────

def verify_dataset() -> dict:
    """验证测试集的基本属性"""
    import importlib.util

    results = {
        "categories": {},
        "errors": [],
        "gt_signatures": {},
    }

    samples_path = OUT_DIR / "samples.jsonl"
    if not samples_path.exists():
        return {"error": "samples.jsonl not found, run build_dataset() first"}

    samples = [json.loads(line) for line in samples_path.read_text(encoding="utf-8").splitlines()]
    results["total"] = len(samples)

    # 统计类别
    for s in samples:
        t = s["scene_type"]
        results["categories"][t] = results["categories"].get(t, 0) + 1

    # 验证 GT 签名
    sigs_path = OUT_DIR / "signatures.json"
    if sigs_path.exists():
        sigs = json.loads(sigs_path.read_text(encoding="utf-8"))
        results["gt_signatures_count"] = len(sigs)
        results["gt_sample"] = list(sigs.values())[0] if sigs else None

    # 验证 npz 文件
    for s in samples[:5]:  # 抽检前5个
        npz_path = OUT_DIR / s["filename"]
        if npz_path.exists():
            try:
                data = np.load(npz_path)
                shape = data["img"].shape
                if shape != (128, 128, 3):
                    results["errors"].append(f"{s['sample_id']}: bad shape {shape}")
            except Exception as e:
                results["errors"].append(f"{s['sample_id']}: {str(e)}")
        else:
            results["errors"].append(f"{s['sample_id']}: file missing")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== 构建 L5 视觉测试集 ===\n")
    result = build_dataset()
    print(f"样本总数: {result['summary']['total_samples']}")
    print("\n类别分布:")
    for k, v in result["summary"]["type_counts"].items():
        print(f"  {k}: {v}")
    print(f"\n输出目录: {result['out_dir']}")

    print("\n=== 验证测试集 ===")
    v = verify_dataset()
    print(f"总数: {v.get('total', '?')}")
    print(f"GT签名数: {v.get('gt_signatures_count', '?')}")
    print(f"类别: {v.get('categories', {})}")
    if v.get("errors"):
        print(f"错误: {v['errors']}")
    else:
        print("无错误")

    print("\n=== GT 签名示例（37°斜面）===")
    sigs = json.loads((OUT_DIR / "signatures.json").read_text(encoding="utf-8"))
    if "A_037" in sigs:
        print(sigs["A_037"])
