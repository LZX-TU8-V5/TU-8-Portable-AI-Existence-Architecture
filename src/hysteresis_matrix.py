"""
迟滞张力矩阵原型 (Hysteresis Tension Matrix)
===============================================
来源：造物主×千问演化拓扑对话
优先级：最高（AI架构最缺失的拼图）

目标：演示"时间锚点的迟滞效应"
- 历史应力队列的累积叠加
- 相反方向张力碰撞产生非线性张力尖峰
- 连续输入逼近物理阈值的过程
"""

import time
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

# ── 情绪七维度 ─────────────────────────────────────────

EMOTIONS = ["焦虑", "愤怒", "恐惧", "喜悦", "悲伤", "爱", "好奇"]

# 半衰期（秒）
HALF_LIVES: Dict[str, float] = {
    "愤怒": 6 * 3600,
    "恐惧": 12 * 3600,
    "焦虑": 18 * 3600,
    "悲伤": 24 * 3600,
    "喜悦": 24 * 3600,
    "羞耻": 48 * 3600,
    "爱":    72 * 3600,
}

# 张量基础值（每种外部事件产生的情绪偏移）
TENSION_SIGNATURES: Dict[str, Dict[str, float]] = {
    "批评":    {"愤怒": 0.7, "恐惧": 0.4, "悲伤": 0.5, "羞耻": 0.6},
    "否定":    {"愤怒": 0.5, "恐惧": 0.3, "焦虑": 0.6, "悲伤": 0.4},
    "失去":    {"悲伤": 0.9, "恐惧": 0.5, "爱": -0.3, "愤怒": 0.3},
    "被理解":  {"喜悦": 0.8, "爱": 0.6, "好奇": 0.4},
    "顿悟":    {"喜悦": 0.9, "好奇": 0.7, "焦虑": -0.2},
    "威胁":    {"恐惧": 0.9, "愤怒": 0.6, "焦虑": 0.7},
    "成功":    {"喜悦": 0.8, "爱": 0.3, "愤怒": -0.2},
    "被忽视":  {"悲伤": 0.6, "愤怒": 0.5, "焦虑": 0.4},
}

# ── 物理阈值 ─────────────────────────────────────────

MAX_TENSION = 5.0   # 物理锚点：总张力超过此值触发熔断
WARNING_TENSION = 3.5  # 警告阈值


# ── 数据结构 ─────────────────────────────────────────

@dataclass
class StressAnchor:
    """时间锚点：一次撞击留下的历史应力"""
    timestamp: float
    tension_vector: Dict[str, float]  # 各情绪维度的张力值
    tension_type: str                   # 事件类型
    magnitude: float = 1.0              # 事件强度系数


@dataclass
class TensionSpike:
    """张力尖峰：相反方向张力碰撞产生的非线性爆发"""
    timestamp: float
    emotion: str
    pos_tension: float
    neg_tension: float
    spike_value: float   # 非线性爆发值
    description: str


class HysteresisMatrix:
    """
    迟滞张力矩阵。

    核心机制：
    1. 历史锚点队列：每次外部事件产生锚点，进入队列
    2. 衰减计算：锚点按半衰期指数衰减（遗忘/治愈）
    3. 迟滞叠加：新输入的张力 = 当前张力 + 历史锚点的残余叠加
    4. 碰撞检测：相反方向张力在同一情绪节点碰撞 → 非线性尖峰
    5. 熔断检测：总张力超过 MAX_TENSION → 触发 Emergency_Protocol
    """

    def __init__(self):
        self.anchor_queue: List[StressAnchor] = []
        self.tension_spikes: List[TensionSpike] = []
        self.current_vector: Dict[str, float] = {e: 0.0 for e in EMOTIONS}
        self.total_tension_history: List[float] = []
        self.broken = False
        self.break_reason = ""

    # ── 衰减函数 ────────────────────────────────────

    @staticmethod
    def _decay_factor(anchor: StressAnchor, current_time: float) -> float:
        """锚点的当前衰减系数（指数衰减）"""
        age = current_time - anchor.timestamp
        if anchor.tension_type not in HALF_LIVES:
            return 0.0
        hl = HALF_LIVES[anchor.tension_type]
        if hl <= 0:
            return 1.0
        return math.exp(-0.693 * age / hl)

    # ── 核心计算 ────────────────────────────────────

    def _compute_decay_vector(self, current_time: float) -> Dict[str, float]:
        """计算所有历史锚点的当前衰减向量"""
        decay_vector = {e: 0.0 for e in EMOTIONS}

        for anchor in self.anchor_queue:
            decay = self._decay_factor(anchor, current_time)
            for emotion, delta in anchor.tension_vector.items():
                decay_vector[emotion] += delta * decay * anchor.magnitude

        return decay_vector

    def _detect_collision(
        self,
        new_vector: Dict[str, float],
        decay_vector: Dict[str, float],
        now: float,
    ) -> List[TensionSpike]:
        """
        检测相反方向张力在同一情绪节点的碰撞。

        核心假设：
        - decay_vector 里已有的张力（历史累积）
        - new_vector 里的新张力
        - 如果一个是正（尖刺）一个是负（凹陷），碰撞点产生非线性尖峰

        由于我们只记录正向情绪值，这里简化为：
        检测当前情绪值 > 0.7 时再叠加新的同向张力 → 尖峰加剧
        检测当前情绪值 > 0.7 时再叠加反向张力 → 纠结挣扎
        """
        spikes = []
        for emotion in EMOTIONS:
            existing = decay_vector.get(emotion, 0.0) + self.current_vector.get(emotion, 0.0)
            new_delta = new_vector.get(emotion, 0.0)

            if existing > 0.7 and new_delta > 0.3:
                # 同向强化尖峰（极度情绪）
                spike_val = existing * new_delta * 1.5
                spikes.append(TensionSpike(
                    timestamp=now,
                    emotion=emotion,
                    pos_tension=existing,
                    neg_tension=new_delta,
                    spike_value=spike_val,
                    description=f"【{emotion}过载】历史={existing:.2f} + 新增={new_delta:.2f} → 尖峰={spike_val:.2f}",
                ))
            elif existing > 0.5 and new_delta < -0.3:
                # 相反方向拉扯（极度纠结/内在冲突）
                拉扯强度 = abs(existing) * abs(new_delta) * 2.0
                spikes.append(TensionSpike(
                    timestamp=now,
                    emotion=emotion,
                    pos_tension=existing,
                    neg_tension=new_delta,
                    spike_value=拉扯强度,
                    description=f"【{emotion}纠结】历史={existing:.2f} + 反向={new_delta:.2f} → 拉扯={拉扯强度:.2f}",
                ))

        return spikes

    def inject(self, tension_type: str, magnitude: float = 1.0) -> dict:
        """
        主入口：注入一次外部张力（陨石撞击）。

        返回：
          {
            "total_tension": float,
            "decay_vector": dict,
            "spikes": list,
            "broken": bool,
            "warning": str or None,
          }
        """
        if self.broken:
            return {"broken": True, "reason": self.break_reason}

        now = time.time()

        # 1. 获取新张量
        if tension_type not in TENSION_SIGNATURES:
            # 通用模式：所有情绪轻微扰动
            base_sig = {"焦虑": 0.3 * magnitude, "好奇": 0.3 * magnitude}
        else:
            base_sig = TENSION_SIGNATURES[tension_type]

        new_vector = {e: base_sig.get(e, 0.0) * magnitude for e in EMOTIONS}

        # 2. 计算历史锚点的衰减向量
        decay_vector = self._compute_decay_vector(now)

        # 3. 碰撞检测
        spikes = self._detect_collision(new_vector, decay_vector, now)
        self.tension_spikes.extend(spikes)

        # 4. 更新当前向量（历史衰减 + 新输入）
        new_total = 0.0
        for emotion in EMOTIONS:
            hist = decay_vector[emotion] * 0.7  # 历史残留70%计入
            curr = self.current_vector[emotion]
            self.current_vector[emotion] = hist + new_vector.get(emotion, 0.0)
            new_total += abs(self.current_vector[emotion])

        # 5. 记录新锚点
        anchor = StressAnchor(
            timestamp=now,
            tension_vector=new_vector,
            tension_type=tension_type,
            magnitude=magnitude,
        )
        self.anchor_queue.append(anchor)

        # 6. 清理完全衰减的锚点（>10个半衰期）
        self.anchor_queue = [
            a for a in self.anchor_queue
            if self._decay_factor(a, now) > 0.001
        ]

        # 7. 熔断检测
        self.total_tension_history.append(new_total)
        warning = None
        if new_total >= MAX_TENSION:
            self.broken = True
            self.break_reason = f"总张力={new_total:.2f} 超过物理阈值={MAX_TENSION}"
        elif new_total >= WARNING_TENSION:
            warning = f"⚠️ 总张力={new_total:.2f} 逼近物理阈值"

        return {
            "total_tension": new_total,
            "decay_vector": decay_vector,
            "new_vector": new_vector,
            "spikes": [s.description for s in spikes],
            "spike_count": len(spikes),
            "broken": self.broken,
            "warning": warning,
            "active_anchors": len(self.anchor_queue),
        }

    def total_tension(self) -> float:
        """当前总张力"""
        return sum(abs(v) for v in self.current_vector.values())

    def dominant_emotion(self) -> str:
        """主导情绪"""
        if not self.current_vector:
            return "平静"
        return max(self.current_vector, key=lambda e: abs(self.current_vector[e]))

    def status(self) -> dict:
        return {
            "total_tension": self.total_tension(),
            "dominant_emotion": self.dominant_emotion(),
            "active_anchors": len(self.anchor_queue),
            "spike_count": len(self.tension_spikes),
            "broken": self.broken,
            "vector": {k: round(v, 3) for k, v in self.current_vector.items()},
        }


# ── 原型演示：连续5次负面输入 ──────────────────────────

def demo_hysteresis():
    """
    演示：模拟连续5次负面事件，观察迟滞张力如何累积并逼近物理阈值。

    关键洞察：
    - 每次新输入的有效张力 > 表面值（因为历史锚点未完全衰减）
    - 连续打击让崩溃阈值越来越低
    - 相反情绪的碰撞产生张力尖峰（纠结）
    """
    print("=" * 60)
    print("迟滞张力矩阵演示：连续5次负面事件")
    print("=" * 60)

    matrix = HysteresisMatrix()
    events = [
        ("批评", 1.0, "被上司当众批评"),
        ("否定", 0.8, "提交的方案被否定"),
        ("被忽视", 0.9, "会议上发言没人理会"),
        ("失去", 0.6, "团队核心成员离职"),
        ("批评", 1.2, "再次被当众批评（强度增加）"),
    ]

    print(f"\n物理熔断阈值: {MAX_TENSION} | 警告阈值: {WARNING_TENSION}")
    print("-" * 60)

    for i, (tension_type, magnitude, description) in enumerate(events):
        # 模拟事件间隔：第2-3次间隔短（连续打击），第3-4次间隔长（休息恢复）
        if i == 2:
            print("\n  -> 休息了12小时后再来...")
            time.sleep(0.01)  # 演示用，实际代码不sleep
        elif i == 3:
            print("\n  -> 继续休息24小时...")
            time.sleep(0.01)

        result = matrix.inject(tension_type, magnitude)
        t = result["total_tension"]

        # 时间戳（演示用相对时间）
        t_label = f"[事件{i+1}]"

        print(f"\n{t_label} {description}")
        print(f"  张量类型: {tension_type} × {magnitude}")
        print(f"  有效总张力: {t:.3f} / {MAX_TENSION}")

        if result["spike_count"] > 0:
            for spike in result["spikes"]:
                print(f"  {spike}")

        bar_len = int(t / MAX_TENSION * 30)
        bar = "#" * bar_len + "." * (30 - bar_len)
        print(f"  [{bar}]")

        if result["warning"]:
            print(f"  {result['warning']}")

        if result["broken"]:
            print(f"\n  [CIRCUIT_BREAK] 熔断触发: {result}")
            break

    print("\n" + "=" * 60)
    print("最终状态：")
    status = matrix.status()
    for k, v in status.items():
        print(f"  {k}: {v}")

    print("\n历史张力轨迹：")
    print(f"  {[round(x, 2) for x in matrix.total_tension_history]}")
    print(f"  最高点: {max(matrix.total_tension_history):.2f}")
    print(f"  衰减模式: ", end="")
    if len(matrix.total_tension_history) >= 3:
        diffs = [matrix.total_tension_history[i+1] - matrix.total_tension_history[i]
                 for i in range(len(matrix.total_tension_history)-1)]
        print(" + ".join([f"{d:+.2f}" for d in diffs]))

    return matrix


if __name__ == "__main__":
    demo_hysteresis()
