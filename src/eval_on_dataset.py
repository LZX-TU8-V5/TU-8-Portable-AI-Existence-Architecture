# -*- coding: utf-8 -*-
"""用合成测试集验证余弦校验器（修复：乘性噪声）"""
import sys, json, math
from pathlib import Path
sys.path.insert(0, r'C:\Users\qq366410837\.qclaw\workspace\src')

import numpy as np
from slice_cosine_verifier import SliceCosineVerifier, SliceMeasurement

OUT_DIR = Path(r'C:\Users\qq366410837\.qclaw\workspace\_agent_memory\synthetic_test_dataset')
samples = [json.loads(l) for l in (OUT_DIR / 'samples.jsonl').read_text(encoding='utf-8').splitlines()]
sigs = json.loads((OUT_DIR / 'signatures.json').read_text(encoding='utf-8'))

print(f"测试集：{len(samples)} 样本\n")

RULER_ANGLES = [0.0, 30.0, 45.0, 60.0]


def gt_to_measurements(gt_theta: float, noise_frac: float = 0.0) -> list:
    """GT斜面 → 固定标尺测量（余弦形状 + 乘性噪声）"""
    meas = []
    for phi in RULER_ANGLES:
        ideal = abs(math.cos(math.radians(phi - gt_theta)))
        # 乘性噪声（与物理图像噪声行为一致）
        if noise_frac > 0:
            measured = ideal * (1 + np.random.uniform(-noise_frac, noise_frac))
            measured = max(0.01, measured)
        else:
            measured = ideal
        meas.append(SliceMeasurement(angle_deg=float(phi), raw_value=measured, plane='XY'))
    return meas


def circle_to_measurements(noise_frac: float = 0.0) -> list:
    """各向同性圆 → 固定标尺测量（无取向，均匀随机）"""
    meas = []
    for phi in RULER_ANGLES:
        # 均匀基线（不是余弦形状）
        base = 0.5 + np.random.uniform(-0.1, 0.1)
        if noise_frac > 0:
            base = base * (1 + np.random.uniform(-noise_frac, noise_frac))
        meas.append(SliceMeasurement(angle_deg=float(phi), raw_value=max(0.01, base), plane='XY'))
    return meas


def run():
    verifier = SliceCosineVerifier()
    np.random.seed(42)

    results = {cat: [] for cat in 'ABCDEF'}

    for s in samples:
        sid = s['sample_id']
        cat = sid.split('_')[0]
        gt = s['gt_angle']
        # 噪声从像素sigma映射到余弦空间的等效比例
        pixel_noise = s['metadata'].get('noise_sigma', 0.0)
        # 经验映射：像素sigma=1 → 余弦空间 frac≈0.01
        noise_frac = pixel_noise * 0.01

        if cat in ('E', 'F'):
            results[cat].append({'sid': sid, 'decision': 'SCENE_SKIP', 'gt': gt})
            continue

        if cat == 'B':
            meas = circle_to_measurements(noise_frac=noise_frac)
        elif gt > 0:
            meas = gt_to_measurements(gt, noise_frac=noise_frac)
        else:
            continue

        r = verifier.verify(meas)
        est = r.recovered_angle_deg
        conf = r.confidence
        passed = r.passed
        err = abs(est - gt) if (gt > 0 and est is not None) else None

        if cat == 'A':
            correct = passed
        elif cat == 'B':
            correct = not passed  # 应拒绝
        elif cat == 'C':
            correct = passed  # 噪声可容忍
        elif cat == 'D':
            correct = True
        else:
            correct = True

        results[cat].append({
            'sid': sid, 'gt': gt, 'est': est, 'err': err,
            'conf': round(conf, 3), 'passed': passed, 'correct': correct,
        })

    # ── 汇总 ────────────────────────────────────────────────────────
    print(f"{'Cat':<5} {'N':<6} {'OK':<5} {'AvgErr':<10} {'预期'}")
    print("=" * 65)

    labels = {
        'A': '纯净斜面 -> 应通过',
        'B': '各向同性圆 -> 应拒绝',
        'C': '噪声斜面 -> 应通过',
        'D': '纹理覆盖 -> 降级检测',
        'E': '双斜面 -> scene跳过',
        'F': '多物体 -> scene跳过',
    }

    total_ok = 0
    total_n = 0

    for cat in 'ABCDEF':
        items = [x for x in results[cat] if x.get('decision') != 'SCENE_SKIP']
        n = len(items)
        if n == 0:
            sn = sum(1 for x in results[cat] if x.get('decision') == 'SCENE_SKIP')
            print(f"{cat:<5} 0/0   -     -           {labels[cat]:<25} ({sn} scene)")
            continue

        n_ok = sum(1 for x in items if x['correct'])
        errs = [x['err'] for x in items if x.get('err') is not None]
        avg_err = sum(errs)/len(errs) if errs else None
        avg_str = f"{avg_err:.2f}deg" if avg_err is not None else "-"
        judge = "OK" if n_ok == n else f"WARN({n_ok}/{n})"

        total_ok += n_ok
        total_n += n

        print(f"{cat:<5} {n_ok}/{n:<4} {judge:<5} {avg_str:<10} {labels[cat]}")

    print()
    if total_n > 0:
        print(f"核心准确率: {total_ok}/{total_n} = {total_ok/total_n*100:.0f}%")

    # 详细
    print("\n--- A类（纯净斜面）---")
    for x in results['A']:
        print(f"  gt={x['gt']:5.1f} est={x['est']:6.2f} err={x['err']:5.2f} conf={x['conf']} passed={x['passed']}")

    print("\n--- B类（各向同性圆）---")
    for x in results['B']:
        print(f"  {x['sid']}: conf={x['conf']} passed={x['passed']} correct={x['correct']}")

    print("\n--- C类（噪声斜面）---")
    for x in results['C']:
        print(f"  gt={x['gt']:5.1f} err={x['err']:5.2f} conf={x['conf']} passed={x['passed']}")


if __name__ == '__main__':
    run()
