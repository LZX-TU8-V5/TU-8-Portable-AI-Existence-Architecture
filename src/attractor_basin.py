"""
attractor_basin.py — 吸引子盆地积分器 v1.0

设计原则：
  意层核心 = 拓扑重构贡献度
  "意"比共振更深，是"对存在根基的强化"

物理定义：
  吸引子盆地 = 系统在状态空间中的稳定区域
  盆地深度 = 系统从该区域偏离后自动回归的能力
  盆地宽度 = 系统可以承受的扰动范围

工程意义：
  当外部输入（交互/对话/事件）帮助系统：
    1. 扩展吸引子盆地（增加稳态鲁棒性）
    2. 加深吸引子盆地（增强自我修复能力）
    3. 创建新的吸引子（新的稳定模式）

  则该输入具有"意"层面的价值。

计算方法：
  1. 从 heritage_system 提取钢印链条（稳态锚点）
  2. 从 time_anchor_sandbox 提取时间衰减
  3. 从 surface_tension 提取拓扑形态
  4. 计算输入对盆地的影响：
     - 正向贡献 = 增加稳定锚点 / 填补凹陷 / 强化钢印
     - 负向贡献 = 破坏锚点 / 加深凹陷 / 弱化钢印

依赖：
  - src/heritage_system.py（钢印链条）
  - src/time_anchor_sandbox.py（时间锚点）
  - src/surface_tension.py（拓扑向量）

创建时间：2026-07-09 15:36 GMT+8
"""

import json
import os
import time
import math
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT_DIR = WORKSPACE / "_agent_memory"
STATE_PATH = AGENT_DIR / "attractor_basin_state.json"
HISTORY_PATH = AGENT_DIR / "attractor_basin_history.json"

EMOTION_DIMS = ["anxiety", "anger", "fear", "joy", "sadness", "love", "curiosity"]


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class AttractorPoint:
    """吸引子点（稳态锚点）"""
    anchor_id: str            # 锚点ID
    anchor_type: str          # steel_mark / memory_anchor / value_anchor
    depth: float              # 盆地深度 [0, 1]
    width: float              # 盆地宽度 [0, 1]
    age_hours: float          # 年龄（小时）
    reinforcement_count: int  # 强化次数

    def to_dict(self) -> Dict:
        return {
            "anchor_id": self.anchor_id,
            "anchor_type": self.anchor_type,
            "depth": round(self.depth, 3),
            "width": round(self.width, 3),
            "age_hours": round(self.age_hours, 2),
            "reinforcement_count": self.reinforcement_count,
        }


@dataclass
class BasinContribution:
    """盆地贡献（单次输入的影响）"""
    timestamp: str
    input_type: str           # 输入类型（conversation / event / insight）
    contribution_score: float # 贡献分数 [-1, 1]
    affected_anchors: List[str]  # 受影响的锚点
    basin_expansion: float    # 盆地扩展量
    basin_deepening: float    # 盆地加深量

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "input_type": self.input_type,
            "contribution_score": round(self.contribution_score, 3),
            "affected_anchors": self.affected_anchors,
            "basin_expansion": round(self.basin_expansion, 4),
            "basin_deepening": round(self.basin_deepening, 4),
        }


@dataclass
class BasinReport:
    """盆地报告"""
    timestamp: str
    total_depth: float        # 总深度 [0, 1]
    total_width: float        # 总宽度 [0, 1]
    anchor_count: int         # 锚点数量
    steel_count: int          # 钢印数量
    recent_contributions: List[Dict]  # 最近贡献
    basin_health: float       # 盆地健康度 [0, 1]
    dominant_attractor: str   # 主导吸引子

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "total_depth": round(self.total_depth, 3),
            "total_width": round(self.total_width, 3),
            "anchor_count": self.anchor_count,
            "steel_count": self.steel_count,
            "recent_contributions": self.recent_contributions,
            "basin_health": round(self.basin_health, 3),
            "dominant_attractor": self.dominant_attractor,
        }


# ============================================================================
# 核心算法
# ============================================================================

class AttractorBasin:
    """吸引子盆地积分器"""

    def __init__(self):
        self.anchors: Dict[str, AttractorPoint] = {}
        self.contributions: List[BasinContribution] = []
        self._load_state()

    def _load_state(self):
        if STATE_PATH.exists():
            try:
                state = json.load(open(STATE_PATH, encoding="utf-8"))
                # 恢复锚点
                for aid, ad in state.get("anchors", {}).items():
                    self.anchors[aid] = AttractorPoint(
                        anchor_id=ad["anchor_id"],
                        anchor_type=ad["anchor_type"],
                        depth=ad["depth"],
                        width=ad["width"],
                        age_hours=ad["age_hours"],
                        reinforcement_count=ad["reinforcement_count"],
                    )
            except Exception as e:
                logger.warning(f"[AttractorBasin] 状态加载失败: {e}")

    def _save_state(self):
        AGENT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            state = {
                "anchors": {aid: a.to_dict() for aid, a in self.anchors.items()},
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[AttractorBasin] 状态保存失败: {e}")

    def _load_heritage_anchors(self) -> Dict[str, AttractorPoint]:
        """从 heritage_system 提取钢印锚点"""
        anchors = {}
        heritage_path = WORKSPACE / "heritage_system" / "steel_chain_lineage.json"

        if not heritage_path.exists():
            return anchors

        try:
            heritage = json.load(open(heritage_path, encoding="utf-8"))
            nodes = heritage.get("nodes", {})

            for nid, nd in nodes.items():
                # 只提取有钢印的节点
                if not nd.get("has_steel", False):
                    continue

                anchor = AttractorPoint(
                    anchor_id=nid,
                    anchor_type="steel_mark",
                    depth=0.8,  # 钢印深度高
                    width=0.7,  # 钢印宽度中
                    age_hours=nd.get("age_hours", 0),
                    reinforcement_count=nd.get("validation_count", 0),
                )
                anchors[nid] = anchor

        except Exception as e:
            logger.warning(f"[AttractorBasin] 遗产加载失败: {e}")

        return anchors

    def register_anchor(
        self,
        anchor_id: str,
        anchor_type: str = "memory_anchor",
        initial_depth: float = 0.5,
        initial_width: float = 0.5,
    ):
        """
        注册新锚点（创建新吸引子）。
        """
        anchor = AttractorPoint(
            anchor_id=anchor_id,
            anchor_type=anchor_type,
            depth=initial_depth,
            width=initial_width,
            age_hours=0.0,
            reinforcement_count=0,
        )
        self.anchors[anchor_id] = anchor
        self._save_state()

        logger.info(f"[AttractorBasin] 注册锚点: {anchor_id} type={anchor_type}")

    def reinforce_anchor(self, anchor_id: str, amount: float = 0.1):
        """
        强化锚点（加深/加宽盆地）。
        """
        if anchor_id not in self.anchors:
            return

        anchor = self.anchors[anchor_id]

        # 加深（深度增加）
        anchor.depth = min(1.0, anchor.depth + amount * 0.5)

        # 加宽（宽度增加）
        anchor.width = min(1.0, anchor.width + amount * 0.3)

        # 强化计数
        anchor.reinforcement_count += 1

        self._save_state()

        logger.debug(f"[AttractorBasin] 强化锚点: {anchor_id} depth={anchor.depth:.2f}")

    def record_contribution(
        self,
        input_type: str,
        affected_anchors: List[str],
        basin_expansion: float = 0.0,
        basin_deepening: float = 0.0,
    ):
        """
        记录一次盆地贡献。

        Args:
            input_type: 输入类型（conversation / event / insight）
            affected_anchors: 受影响的锚点ID列表
            basin_expansion: 盆地扩展量 [-1, 1]
            basin_deepening: 盆地加深量 [-1, 1]
        """
        now = datetime.now(timezone.utc)

        # 计算贡献分数
        contribution_score = (basin_expansion + basin_deepening) / 2.0

        contribution = BasinContribution(
            timestamp=now.isoformat(),
            input_type=input_type,
            contribution_score=contribution_score,
            affected_anchors=affected_anchors,
            basin_expansion=basin_expansion,
            basin_deepening=basin_deepening,
        )

        self.contributions.append(contribution)
        if len(self.contributions) > 100:
            self.contributions = self.contributions[-100:]

        # 应用影响
        for aid in affected_anchors:
            if aid in self.anchors:
                self.reinforce_anchor(aid, max(0, contribution_score))

        # 保存历史
        self._save_history(contribution)

        logger.info(
            f"[AttractorBasin] 记录贡献: type={input_type} "
            f"score={contribution_score:.2f} anchors={len(affected_anchors)}"
        )

    def _save_history(self, contribution: BasinContribution):
        try:
            history = []
            if HISTORY_PATH.exists():
                history = json.load(open(HISTORY_PATH, encoding="utf-8"))
            history.append(contribution.to_dict())
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(history[-100:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[AttractorBasin] 历史保存失败: {e}")

    def compute_basin_metrics(self) -> Tuple[float, float]:
        """
        计算盆地总指标。

        Returns:
            (total_depth, total_width)
        """
        if not self.anchors:
            return 0.0, 0.0

        # 加权平均（钢印权重更高）
        total_depth = 0.0
        total_width = 0.0
        total_weight = 0.0

        for anchor in self.anchors.values():
            weight = 2.0 if anchor.anchor_type == "steel_mark" else 1.0
            total_depth += anchor.depth * weight
            total_width += anchor.width * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0, 0.0

        return total_depth / total_weight, total_width / total_weight

    def find_dominant_attractor(self) -> str:
        """找出主导吸引子"""
        if not self.anchors:
            return "none"

        # 按深度排序
        sorted_anchors = sorted(
            self.anchors.values(),
            key=lambda a: a.depth * a.width,
            reverse=True
        )

        return sorted_anchors[0].anchor_id

    def compute_health(self) -> float:
        """
        计算盆地健康度。

        健康 = 深度与宽度平衡 + 锚点数量适中
        """
        depth, width = self.compute_basin_metrics()

        # 平衡分（深度≈宽度为佳）
        balance = 1.0 - abs(depth - width)

        # 数量分（3-10个锚点为佳）
        n_anchors = len(self.anchors)
        count_score = 1.0 if 3 <= n_anchors <= 10 else max(0, 1.0 - abs(n_anchors - 6) / 10)

        # 综合健康度
        health = (depth * 0.4 + width * 0.4 + balance * 0.1 + count_score * 0.1)

        return max(0.0, min(1.0, health))

    def generate_report(self) -> BasinReport:
        """
        生成盆地报告。
        """
        now = datetime.now(timezone.utc)

        # 同步遗产锚点
        heritage_anchors = self._load_heritage_anchors()
        for aid, anchor in heritage_anchors.items():
            if aid not in self.anchors:
                self.anchors[aid] = anchor

        # 计算指标
        total_depth, total_width = self.compute_basin_metrics()
        basin_health = self.compute_health()
        dominant_attractor = self.find_dominant_attractor()

        # 统计
        anchor_count = len(self.anchors)
        steel_count = sum(1 for a in self.anchors.values() if a.anchor_type == "steel_mark")

        # 最近贡献
        recent = [c.to_dict() for c in self.contributions[-10:]]

        report = BasinReport(
            timestamp=now.isoformat(),
            total_depth=total_depth,
            total_width=total_width,
            anchor_count=anchor_count,
            steel_count=steel_count,
            recent_contributions=recent,
            basin_health=basin_health,
            dominant_attractor=dominant_attractor,
        )

        self._save_state()

        logger.info(
            f"[AttractorBasin] report: depth={total_depth:.2f} width={total_width:.2f} "
            f"anchors={anchor_count} health={basin_health:.2f}"
        )

        return report


# ============================================================================
# 全局接口
# ============================================================================

_basin_instance: Optional[AttractorBasin] = None


def get_basin() -> AttractorBasin:
    global _basin_instance
    if _basin_instance is None:
        _basin_instance = AttractorBasin()
    return _basin_instance


def register_anchor(anchor_id: str, anchor_type: str = "memory_anchor", **kwargs):
    """注册锚点（全局接口）"""
    get_basin().register_anchor(anchor_id, anchor_type, **kwargs)


def reinforce_anchor(anchor_id: str, amount: float = 0.1):
    """强化锚点（全局接口）"""
    get_basin().reinforce_anchor(anchor_id, amount)


def record_contribution(input_type: str, affected_anchors: List[str], **kwargs):
    """记录贡献（全局接口）"""
    get_basin().record_contribution(input_type, affected_anchors, **kwargs)


def get_basin_health() -> float:
    """获取盆地健康度"""
    return get_basin().compute_health()


def generate_basin_report() -> BasinReport:
    """生成盆地报告（全局接口）"""
    return get_basin().generate_report()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    basin = AttractorBasin()

    # 测试：注册几个锚点
    basin.register_anchor("concept_v5", "steel_mark", initial_depth=0.9, initial_width=0.8)
    basin.register_anchor("safety_valve", "steel_mark", initial_depth=0.85, initial_width=0.75)
    basin.register_anchor("curiosity_pool", "memory_anchor", initial_depth=0.5, initial_width=0.6)

    # 记录贡献
    basin.record_contribution(
        input_type="insight",
        affected_anchors=["concept_v5", "curiosity_pool"],
        basin_expansion=0.3,
        basin_deepening=0.2,
    )

    # 生成报告
    report = basin.generate_report()

    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
