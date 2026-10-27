# synaptic_confidence_updater.py — P1-D0 R2：突触可塑性更新器
# =============================================================================
# 定位：dual_track_confidence_updater.py 的数学内核升级版
#         继承路由/冷却/状态逻辑，只替换核心公式
#
# 核心改动：
#   通路A：α×(1-C)×S  →  LTP/LTD 双阈值模型
#   通路B：0.15+β×T    →  Hebbian + 强制纠错双模式
#
# 阈值常量（与 state_machine / explainer 同步）：
#   θ_LTP = 0.70, θ_LTD = 0.30, θ_H = 0.80
#
# 版本：v1.0 | 2026-07-10 | 来源：R2需求 × 用户反例验证
# =============================================================================

import sys
from pathlib import Path
from typing import Optional

WORKSPACE = Path(r"C:\Users\qq366410837\.qclaw\workspace")
sys.path.insert(0, str(WORKSPACE / "src"))

# 继承非数学逻辑
from dual_track_confidence_updater import (
    DualTrackConfidenceUpdater,
    ConfidenceUpdate,
    DreamSignalContext,
    DreamPhase,
)


# =============================================================================
# SynapticConfidenceUpdater
# =============================================================================

class SynapticConfidenceUpdater(DualTrackConfidenceUpdater):
    """
    突触可塑性版本（v2.0）

    继承 v1.1 的全部非数学逻辑（阶段路由、冷却期、状态持久化、统计）
    只替换两个数学内核：_compute_track_a 和 _compute_track_b

    兼容性：与 DualTrackConfidenceUpdater 完全 API 兼容
             process_dream_signal() / update() / update_track_A/B() 全部复用
    """

    # ── 通路A：LTP/LTD 双阈值常量 ──────────────────────────────────
    THETA_LTP = 0.70   # LTP 触发阈值（Ca²⁺ 类比：S >= θ_LTP → 长时程增强）
    THETA_LTD = 0.30   # LTD 触发阈值（Ca²⁺ 类比：S <= θ_LTD → 长时程抑制）
    LTP = 0.25         # 长时程增强系数
    LTD = 0.05         # 长时程抑制系数

    # ── 通路B：Hebbian + 强制纠错常量 ──────────────────────────────
    THETA_HOMEOSTATIC = 0.80  # 稳态打破阈值（Stress 触发点）
    GAMMA = 0.30        # Hebbian 系数
    LTP_BASE = 0.10     # 通路B 固定基底

    # ── 强制纠错参数 ──────────────────────────────────────────────
    BREAKTHROUGH_BOOST = 0.25  # 强制纠错基础量（独立于C）
    BREAKTHROUGH_SCALE = 0.30  # 强制纠错张力乘数

    # ── 边界裁剪 ──────────────────────────────────────────────────
    CONF_MAX = 0.95     # 与 v1.1 保持一致

    def _compute_track_a(self, C: float, S: float) -> float:
        """
        通路A：钙离子双阈值模型（替代 α×(1-C)×S）

        生物学原理：
          Ca²⁺ < θ_LTD  →  低频刺激  →  LTD（轻微削弱弱连接，节约能量）
          Ca²⁺ > θ_LTP  →  高频爆发  →  LTP（长时程增强，强化新连接）
          θ_LTD < S < θ_LTP  →  双向窗口  →  不稳定，不更新

        数学表达：
            if S >= θ_LTP:
                ΔC = +LTP × C × (1 - C)   ← LTP
            elif S <= θ_LTD:
                ΔC = -LTD × C × S           ← LTD（削弱弱连接）
            else:
                ΔC = 0.0                    ← 双向窗口，不更新

        设计理由：
          - C×(1-C)：在高置信度（C→1）和低置信度（C→0）时趋近0，
                      在 C=0.5 时最大（最可塑），符合神经可塑性规律
          - LTD 对弱连接（S小，C小）削弱最多，节约突触能量
          - 双向窗口：不稳定状态不更新，等待信号清晰
        """
        # 双向窗口：不稳定态，暂停更新
        if self.THETA_LTD < S < self.THETA_LTP:
            return 0.0

        # LTD：低频刺激，削弱弱连接
        if S <= self.THETA_LTD:
            delta = -self.LTD * C * S
            return delta

        # LTP：高频爆发，强化连接
        if S >= self.THETA_LTP:
            delta = self.LTP * C * (1 - C)
            return delta

        # 兜底（理论上不会走到这里）
        return 0.0

    def _compute_track_b(
        self,
        T: float,
        C: Optional[float] = None,  # 新增：C_before 注入（强制纠错时需要）
    ) -> float:
        """
        通路B：稳态调节 + 强制纠错双模式（替代 0.15+β×T）

        漏洞修复（用户反例）：
          旧公式：ΔC = 0.15 + β × T × C × (1-C)
          C=0.99, T=1.0 → ΔC ≈ 0.01（稳态保护高置信度，无法纠错）

          新公式：T >= θ_H → 强制纠错，绕过 Hebbian 项
          C=0.99, T=1.0 → ΔC = -(0.25 + 0.30×1.0) = -0.55（有效纠错）

        两种模式：
          常态（T < θ_H）：Hebbian 稳态调节
            ΔC = LTP_BASE + γ × T × C × (1-C)
            - C×(1-C)：在 C=0.5 时最大（最可塑区间），强化效果最强
            - T：矛盾深度，调解强化强度

          强制纠错（T >= θ_H）：应激反应
            ΔC = -(BREAKTHROUGH_BOOST + BREAKTHROUGH_SCALE × T)
            - 不再经过 C×(1-C) 的抑制门
            - T 直接驱动强制下调
            - 生物学类比：肾上腺素绕过常规神经调节，直接驱动应激反应
        """
        # ── 强制纠错模式（稳态打破）───────────────────────────────
        if T >= self.THETA_HOMEOSTATIC:
            delta_breakthrough = -(
                self.BREAKTHROUGH_BOOST
                + self.BREAKTHROUGH_SCALE * T
            )
            return delta_breakthrough

        # ── 常态Hebbian模式 ─────────────────────────────────────
        # C=0.5 时 C×(1-C)=0.25 最大（最可塑）
        # C→0 或 C→1 时趋近0（稳态保护）
        if C is None:
            C = 0.5  # 默认值（与旧版兼容）

        hebb = self.GAMMA * T * C * (1 - C)
        return self.LTP_BASE + hebb

    # ── 兼容旧版接口 ─────────────────────────────────────────────

    def _compute_track_b_legacy(self, T: float) -> float:
        """旧版 _compute_track_b 签名（无 C 参数）"""
        return self._compute_track_b(T, C=None)



# =============================================================================
# 测试验证
# =============================================================================

if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )

    print("=" * 60)
    print("SynapticConfidenceUpdater 突触可塑性验证")
    print("=" * 60)

    updater = SynapticConfidenceUpdater()

    # ── 通路A测试：LTP/LTD 双阈值 ──────────────────────────────────
    print("\n【通路A：LTP/LTD 双阈值】")
    C = 0.5  # 中等置信度

    track_a_cases = [
        ("S=0.80（LTP触发）", 0.80),
        ("S=0.70（LTP边界）", 0.70),
        ("S=0.29（LTD触发）", 0.29),
        ("S=0.30（LTD边界）", 0.30),
        ("S=0.50（双向窗口→0）", 0.50),
        ("S=0.20（<LTD→LTD）", 0.20),
    ]

    print(f"\n  C={C} 时不同S值对应的ΔC：")
    for label, S in track_a_cases:
        delta = updater._compute_track_a(C, S)
        print(f"    {label} → ΔC={delta:+.4f}")

    # ── 通路B测试：Hebbian + 强制纠错 ─────────────────────────────
    print("\n【通路B：Hebbian + 强制纠错】")

    # 用户反例：旧版无法纠错，新版必须能纠
    C_high = 0.99
    C_mid = 0.50

    print(f"\n  C={C_high}（高置信度）时不同T值对应的ΔC：")
    track_b_cases = [
        ("T=0.20（常态-Hebbian）", 0.20),
        ("T=0.50（常态-Hebbian）", 0.50),
        ("T=0.79（常态边界）", 0.79),
        ("T=0.80（临界→强制纠错）", 0.80),
        ("T=0.90（强制纠错）", 0.90),
        ("T=1.00（强制纠错）", 1.00),
    ]

    for label, T in track_b_cases:
        delta = updater._compute_track_b(T, C=C_high)
        C_new = C_high + delta
        print(f"    {label} → ΔC={delta:+.4f}, C_new={C_new:.3f}")

    print(f"\n  C={C_mid}（中等置信度）时T=0.80的ΔC：")
    delta_mid = updater._compute_track_b(0.80, C=C_mid)
    print(f"    T=0.80, C={C_mid} → ΔC={delta_mid:+.4f}, C_new={C_mid+delta_mid:.3f}")

    # ── 关键验证：旧版漏洞 vs 新版修复 ─────────────────────────────
    print("\n【关键验证：用户反例】")

    # 旧版公式（旧 _compute_track_b）
    C_test = 0.99
    T_test = 1.0
    gamma = 0.30
    ltp_base = 0.10

    old_delta = ltp_base + gamma * T_test * C_test * (1 - C_test)
    new_delta = updater._compute_track_b(T_test, C=C_test)
    C_new_old = C_test + old_delta
    C_new_new = C_test + new_delta

    print(f"\n  用户反例：C={C_test}, T={T_test}")
    print(f"  旧版公式：ΔC={old_delta:+.4f} → C_new={C_new_old:.4f}")
    print(f"  新版公式：ΔC={new_delta:+.4f} → C_new={C_new_new:.4f}")
    print(f"  旧版纠错量：|{C_test}-{C_new_old:.4f}|={abs(C_test-C_new_old):.4f}")
    print(f"  新版纠错量：|{C_test}-{C_new_new:.4f}|={abs(C_test-C_new_new):.4f}")

    if abs(new_delta) > abs(old_delta) * 10:
        print(f"  ✓ 新版纠错能力提升 {abs(new_delta)/abs(old_delta):.0f} 倍")
    else:
        print(f"  ✗ 纠错能力提升不足")

    # ── C×(1-C) 可塑性曲线验证 ──────────────────────────────────
    print("\n【C×(1-C) 可塑性曲线验证】")
    print("  预期：C=0.5时Hebbian最强，C→0或C→1时趋弱")

    C_vals = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
    T_fixed = 0.5
    print(f"\n  T={T_fixed} 时，不同C值对应的Hebbian项（γ×T×C×(1-C)）：")
    for C_v in C_vals:
        hebb = gamma * T_fixed * C_v * (1 - C_v)
        print(f"    C={C_v:.1f} → Hebbian={hebb:+.4f}  {'← 最可塑' if C_v == 0.5 else ''}")

    print()
