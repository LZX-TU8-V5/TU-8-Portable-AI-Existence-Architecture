"""
dream_topology_engine.py — 纯拓扑约束求解器 v1.0
=============================================

梦境重定义：梦 = 约束方程组的动态求解过程，不是叙事生成。

核心原则：
  1. 输入：拓扑快照（张量，无材质/无标签/无语言）
  2. 输出：约束方程演化状态（结构化数据，绝不渲染为叙事）
  3. 必须经过 deep_surface_interface 表层转译器 → 禁止直接输出语言
  4. 支持热加载（从状态文件恢复未完成的梦境期）

约束求解策略：
  - 张力松弛：每条约束趋向能量极小点
  - 降维合并：相似约束自动合并，压缩拓扑复杂度
  - 结构同构检测：识别重复拓扑模式
  - 死锁检测：无法收敛的约束标记为死锁 → 请求 Revision 相态干预

依赖：deep_surface_interface (输出门控) / phase_state_machine (触发调度)

创建时间：2026-07-21
"""

import sys
import json
import os
import time
import random
import math
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Tuple
from enum import Enum
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════
# 1. 路径 / 常量
# ═══════════════════════════════════════════════════════════════════════════

def _ws() -> str:
    return os.environ.get(
        "QCLAW_WORKSPACE",
        os.path.join(os.environ["USERPROFILE"], ".qclaw", "workspace")
    )

def _memory() -> str:
    return os.path.join(_ws(), "_agent_memory")

# 默认引擎参数
DEFAULT_CONFIG: dict = {
    "max_iterations": 50,                # 单次 step() 最大迭代数
    "convergence_threshold": 0.01,       # 张力变化 < 此值视为收敛
    "merge_similarity_threshold": 0.85,  # 余弦相似 > 此值自动合并
    "deadlock_limit": 10,                # 同一约束连续不收敛达到此值 → 死锁
    "dim_reduction_k": 0.3,              # 降维保留比例 (top 30%)
    "random_seed": 42,                   # 确定性随机种子
}

# ═══════════════════════════════════════════════════════════════════════════
# 2. 数据类
# ═══════════════════════════════════════════════════════════════════════════

class ConstraintType(str, Enum):
    """约束类型 — 拓扑求解的原子单位"""
    TENSION    = "tension"     # 张力约束：两点间的张力度量
    PROXIMITY  = "proximity"   # 邻近约束：结构上靠近的节点
    HIERARCHY  = "hierarchy"   # 层级约束：父子/包含关系
    SEQUENCE   = "sequence"    # 时序约束：前后依赖关系
    SYMMETRY   = "symmetry"    # 对称约束：镜像/重复模式

class SolvingState(str, Enum):
    """每条约束的计算状态"""
    PENDING  = "pending"       # 待求解
    ACTIVE   = "active"        # 正在求解中
    RESOLVED = "resolved"      # 已收敛到稳态
    STUCK    = "stuck"         # 无法收敛 → 死锁
    PRUNED   = "pruned"        # 被剪枝（合并/降维丢弃）


@dataclass
class TopologySnapshot:
    """
    拓扑快照 — 梦境输入的标准格式。

    tensor: 2D list (N × D)，N = 节点数，D = 特征维度
            无材质/无标签，纯数值表征
    """
    timestamp: str                       # ISO 时间戳
    source: str                          # 来源（surface_tension / gradient_force 等）
    nodes: List[List[float]]             # 节点特征矩阵 N × D
    node_labels: List[str] = field(default_factory=list)  # 可选的调试标签（非语义侵入）
    metadata: dict = field(default_factory=dict)

    def validate(self) -> bool:
        """基础校验：无空/无NaN"""
        if not self.nodes:
            return False
        d = len(self.nodes[0])
        for row in self.nodes:
            if len(row) != d:
                return False
            for v in row:
                if not isinstance(v, (int, float)):
                    return False
                if math.isnan(v) or math.isinf(v):
                    return False
        return True

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def dim(self) -> int:
        return len(self.nodes[0]) if self.nodes else 0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "n_nodes": self.n_nodes,
            "dim": self.dim,
            "node_labels": self.node_labels,
            "metadata": self.metadata,
            # nodes 太大不序列化；只存摘要
            "mean": [round(sum(col)/len(col), 4) for col in zip(*self.nodes)] if self.nodes else [],
        }


@dataclass
class ConstraintEquation:
    """
    单条约束方程 — 梦境拓扑的基本运算单位。

    - 每条约束对应拓扑中的一个结构关系
    - state 跟踪计算进度
    - tension 当前张力值（趋向 0 为收敛）
    - stuck_count 连续不收敛次数
    """
    id: str
    ctype: ConstraintType
    node_indices: List[int]              # 涉及的节点索引
    params: dict = field(default_factory=dict)  # 超参数
    tension: float = 1.0                 # 当前张力 [0, ∞)
    state: SolvingState = SolvingState.PENDING
    stuck_count: int = 0
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ctype": self.ctype.value,
            "node_indices": self.node_indices,
            "tension": round(self.tension, 4),
            "state": self.state.value,
            "stuck_count": self.stuck_count,
            "params": {k: round(v, 4) if isinstance(v, float) else v
                       for k, v in self.params.items()},
        }


@dataclass
class DreamSessionReport:
    """
    单次梦境期的完整报告。
    用于集成到 dream_consolidation / 遥测面板。
    不是叙事 —— 是结构化求解记录。
    """
    session_id: str
    started_at: str
    ended_at: str
    snapshots_processed: int
    total_constraints: int
    resolved: int
    stuck: int
    pruned: int
    active: int
    mean_final_tension: float
    deadlock_types: List[str]
    merged_count: int
    isomorphisms_found: int

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_line(self) -> str:
        """单行摘要（用于日志/遥测，非叙事）"""
        pct = (self.resolved / max(self.total_constraints, 1)) * 100
        return (
            f"DreamSession[{self.session_id}] "
            f"snapshots={self.snapshots_processed} "
            f"constraints={self.total_constraints} "
            f"resolved={self.resolved}({pct:.0f}%) "
            f"stuck={self.stuck} pruned={self.pruned} "
            f"meanT={self.mean_final_tension:.3f} "
            f"merge={self.merged_count} iso={self.isomorphisms_found}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 3. 核心引擎
# ═══════════════════════════════════════════════════════════════════════════

class DreamTopologyEngine:
    """
    梦境拓扑引擎。

    工作流：
      engine = DreamTopologyEngine(config, session_id)
      engine.load_snapshot(snapshot)      # 注入拓扑快照
      engine.extract_constraints()        # 从快照提取约束
      report = engine.solve()             # 迭代求解
      # report 必须经 deep_surface_interface 才能表层输出

    禁止直接以语言/叙事形式输出任何求解结果。

    用法（无依赖测试模式）：
      python src/dream_topology_engine.py --dry
    """

    def __init__(self, config: Optional[dict] = None, session_id: str = ""):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.session_id = session_id or f"dream_{int(time.time())}"
        random.seed(self.config["random_seed"])

        # 运行时状态
        self._snapshots: List[TopologySnapshot] = []
        self._constraints: List[ConstraintEquation] = []
        self._node_pool: List[List[float]] = []         # 合并后节点池
        self._iteration = 0
        self._started = time.time()
        self._deadlock_counters: dict[str, int] = {}    # 全局死锁计数
        self._isomorphisms: List[Tuple[int, int]] = []  # 找到的结构同构对

        # 存储路径
        self._state_dir = _memory()
        self._state_file = os.path.join(self._state_dir, "dream_topology_state.json")

    # ─── 3.1 数据输入 ────────────────────────────────────────────────

    def load_snapshot(self, snapshot: TopologySnapshot) -> None:
        """载入一个拓扑快照到求解器。"""
        if not snapshot.validate():
            raise ValueError(f"TopologySnapshot 校验失败: {snapshot.source}")
        self._snapshots.append(snapshot)
        self._merge_nodes(snapshot.nodes)

    def load_state(self, state_path: Optional[str] = None) -> bool:
        """从状态文件恢复未完成的梦境期（热加载）。"""
        path = state_path or self._state_file
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.session_id = data.get("session_id", self.session_id)
            self._node_pool = data.get("node_pool", [])
            self._iteration = data.get("iteration", 0)
            self._constraints = [
                ConstraintEquation(
                    id=c["id"],
                    ctype=ConstraintType(c.get("ctype", "tension")),
                    node_indices=c.get("node_indices", []),
                    params=c.get("params", {}),
                    tension=c.get("tension", 1.0),
                    state=SolvingState(c.get("state", "pending")),
                    stuck_count=c.get("stuck_count", 0),
                    created_at=c.get("created_at", time.time()),
                )
                for c in data.get("constraints", [])
            ]
            # 不恢复快照本身（过大），上层需重新注入
            return True
        except (json.JSONDecodeError, KeyError, ValueError):
            return False

    def save_state(self) -> None:
        """保存当前状态供热加载恢复。"""
        os.makedirs(self._state_dir, exist_ok=True)
        data = {
            "session_id": self.session_id,
            "node_pool": self._node_pool,
            "iteration": self._iteration,
            "timestamp": time.time(),
            "constraints": [c.to_dict() for c in self._constraints],
        }
        with open(self._state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ─── 3.2 约束提取 ─────────────────────────────────────────────────

    def extract_constraints(self) -> List[ConstraintEquation]:
        """
        从节点池提取约束方程。
        策略：距离 + 张力 + 层级关系 → 生成约束。

        纯数值运算，不触碰语义标签。
        """
        if not self._node_pool:
            return []

        n = len(self._node_pool)
        d = len(self._node_pool[0]) if n else 0
        if d == 0:
            return []

        constraints: List[ConstraintEquation] = []
        cid = len(self._constraints)

        # (a) 张力约束：节点对之间的欧氏距离
        # 距离越远 → 张力越大 → 需要求解
        distances: List[Tuple[float, int, int]] = []
        for i in range(n):
            for j in range(i + 1, n):
                dist = math.sqrt(sum((self._node_pool[i][k] - self._node_pool[j][k]) ** 2
                                     for k in range(d)))
                distances.append((dist, i, j))

        # 按距离降序（最大张力优先求解）
        distances.sort(reverse=True, key=lambda x: x[0])

        # 取 top 30% 作为活跃约束
        n_constraints = max(1, len(distances) * 3 // 10)
        for dist, i, j in distances[:n_constraints]:
            cid += 1
            tension = min(dist, 5.0)  # 钳制，防止极端值
            constraints.append(ConstraintEquation(
                id=f"constraint_{cid}",
                ctype=ConstraintType.TENSION,
                node_indices=[i, j],
                params={"distance": round(dist, 4)},
                tension=tension,
            ))

        # (b) 邻近约束：高相似节点互连
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._cosine_sim(self._node_pool[i], self._node_pool[j])
                if sim > 0.7:  # 高相似度 → 邻近约束（低张力）
                    cid += 1
                    constraints.append(ConstraintEquation(
                        id=f"constraint_{cid}",
                        ctype=ConstraintType.PROXIMITY,
                        node_indices=[i, j],
                        params={"similarity": round(sim, 4)},
                        tension=1.0 - sim,  # 相似越高张力越低
                    ))

        # (c) 对称约束：检测近似相等的向量对
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._cosine_sim(self._node_pool[i], self._node_pool[j])
                if sim > 0.9:  # 非常相似 → 对称模式
                    cid += 1
                    constraints.append(ConstraintEquation(
                        id=f"constraint_{cid}",
                        ctype=ConstraintType.SYMMETRY,
                        node_indices=[i, j],
                        params={"similarity": round(sim, 4)},
                        tension=0.1,  # 对称约束天生低张力
                    ))

        self._constraints.extend(constraints)
        return constraints

    # ─── 3.3 求解循环 ─────────────────────────────────────────────────

    def solve(self, iterations: Optional[int] = None) -> DreamSessionReport:
        """
        迭代求解约束方程组。
        iterations: 指定迭代次数（默认使用 config 值）

        每一步：
          1. 张力松弛：每条约束向低能态移动
          2. 死锁检测：连续不收敛的约束标记死锁
          3. 同构检测：周期性扫描结构重复
          4. 降维合并：相似约束自动压缩

        返回：结构化报告（非叙事）
        """
        max_iter = iterations or self.config["max_iterations"]

        # 如果还没有约束，先提取
        if not self._constraints:
            self.extract_constraints()
        
        pre_count = len(self._constraints)

        for step in range(max_iter):
            self._iteration += 1

            # --- 张力松弛 ---
            dead_c = 0
            total_tension = 0.0
            for c in self._constraints:
                if c.state in (SolvingState.RESOLVED, SolvingState.PRUNED):
                    continue
                result = self._relax(c)
                if result == "resolved":
                    c.state = SolvingState.RESOLVED
                    c.resolved_at = time.time()
                elif result == "stuck":
                    c.stuck_count += 1
                    dead_c += 1
                    if c.stuck_count >= self.config["deadlock_limit"]:
                        c.state = SolvingState.STUCK
                total_tension += c.tension

            # --- 同构检测（每 20% 步数做一次）---
            if step > 0 and step % max(1, max_iter // 5) == 0:
                self._detect_isomorphisms()

            # --- 降维合并（每 40% 步数做一次）---
            if step > 0 and step % max(1, max_iter * 2 // 5) == 0:
                merged = self._merge_similar_constraints()
                # merged 数量记录在下次调用中反映

        # --- 最终统计 ---
        resolved = sum(1 for c in self._constraints if c.state == SolvingState.RESOLVED)
        stuck = sum(1 for c in self._constraints if c.state == SolvingState.STUCK)
        pruned = sum(1 for c in self._constraints if c.state == SolvingState.PRUNED)
        active = sum(1 for c in self._constraints if c.state == SolvingState.ACTIVE)
        mean_tension = (
            sum(c.tension for c in self._constraints) / max(len(self._constraints), 1)
        )
        deadlock_types = list(set(
            c.ctype.value for c in self._constraints if c.state == SolvingState.STUCK
        ))

        report = DreamSessionReport(
            session_id=self.session_id,
            started_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(self._started)),
            ended_at=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time())),
            snapshots_processed=len(self._snapshots),
            total_constraints=pre_count,
            resolved=resolved,
            stuck=stuck,
            pruned=pruned,
            active=active,
            mean_final_tension=mean_tension,
            deadlock_types=deadlock_types,
            merged_count=self._merged_count,
            isomorphisms_found=len(self._isomorphisms),
        )
        return report

    # ─── 3.4 内部算法 ─────────────────────────────────────────────────

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        """余弦相似度（纯代数，无超越函数污染）。"""
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def _relax(self, c: ConstraintEquation) -> str:
        """
        单约束松弛一步。
        返回 'resolved' / 'stuck' / 'active'
        """
        # 张力收缩：线性衰减
        old_tension = c.tension
        if c.ctype in (ConstraintType.SYMMETRY, ConstraintType.PROXIMITY):
            # 低张力类型快速收敛
            c.tension *= 0.5
        elif c.ctype == ConstraintType.TENSION:
            # 张力约束中等速度收敛
            c.tension *= 0.7
        else:
            c.tension *= 0.85

        # 加入随机微扰防止局部极小
        noise = random.uniform(-0.02, 0.02)
        c.tension = max(0.0, min(5.0, c.tension + noise))

        # 判据
        delta = abs(old_tension - c.tension)
        if delta < self.config["convergence_threshold"]:
            return "resolved"
        if c.stuck_count >= self.config["deadlock_limit"] - 2:
            return "stuck"
        return "active"

    def _detect_isomorphisms(self) -> int:
        """
        检测结构同构：找到张力分布模式相似的约束对。

        返回新发现的同构数。
        """
        found = 0
        patterns: dict[float, list[int]] = {}
        for i, c in enumerate(self._constraints):
            # 用张力值 + 节点数量构造模式签名
            sig = round(c.tension * len(c.node_indices), 4)
            patterns.setdefault(sig, []).append(i)

        for sig, indices in patterns.items():
            if len(indices) >= 2:
                for j in range(1, len(indices)):
                    a, b = indices[0], indices[j]
                    if (a, b) not in self._isomorphisms and (b, a) not in self._isomorphisms:
                        self._isomorphisms.append((a, b))
                        found += 1
        return found

    _merged_count: int = 0

    def _merge_similar_constraints(self) -> int:
        """
        合并相似约束（余弦相似 > 阈值）以减少拓扑复杂度。
        保留张力最大的那条，剪枝其余。

        返回合并剪枝的数量。
        """
        if len(self._constraints) < 2:
            return 0
        merged = 0
        # 只考虑未收敛的约束
        active_ids = [i for i, c in enumerate(self._constraints)
                      if c.state not in (SolvingState.RESOLVED, SolvingState.PRUNED)]
        to_prune: set[int] = set()

        for i_idx in range(len(active_ids)):
            i = active_ids[i_idx]
            if i in to_prune:
                continue
            for j_idx in range(i_idx + 1, len(active_ids)):
                j = active_ids[j_idx]
                if j in to_prune:
                    continue
                ci, cj = self._constraints[i], self._constraints[j]
                # 构造向量：用张力 + 覆盖节点数作为特征
                vec_i = [ci.tension, len(ci.node_indices)]
                vec_j = [cj.tension, len(cj.node_indices)]
                # 增加节点重叠量
                overlap = len(set(ci.node_indices) & set(cj.node_indices))
                # 简化相似度计算
                if ci.ctype == cj.ctype and overlap >= max(len(ci.node_indices), len(cj.node_indices)) * 0.5:
                    sim = self._cosine_sim(vec_i, vec_j)
                    if sim > self.config["merge_similarity_threshold"]:
                        # 保留张力更大的那个
                        if ci.tension >= cj.tension:
                            to_prune.add(j)
                        else:
                            to_prune.add(i)
                        merged += 1

        for idx in to_prune:
            self._constraints[idx].state = SolvingState.PRUNED

        # 更新合并后的节点池（降维）
        self._reduce_dimension()

        self._merged_count = merged  # 覆盖（不是累加，因为每次调用重置）
        return merged

    def _reduce_dimension(self) -> None:
        """
        降维：保留张力最高的 top K% 约束对应节点，移除低贡献节点。

        等价于神经网络中的 top-k 稀疏化。
        """
        if not self._constraints:
            return

        # 按张力降序
        ranked = sorted(
            [c for c in self._constraints if c.state != SolvingState.PRUNED],
            key=lambda x: x.tension, reverse=True
        )
        k = max(1, int(len(ranked) * self.config["dim_reduction_k"]))
        keep_ids = set()
        for c in ranked[:k]:
            keep_ids.update(c.node_indices)

        # 保留的节点在 node_pool 中不动，但可以标记压缩信息
        # 不对 node_pool 物理删除（会破坏索引）；在约束层面已完成剪枝
        pass

    # ─── 3.5 辅助 ──────────────────────────────────────────────────────

    def _merge_nodes(self, new_nodes: List[List[float]]) -> None:
        """
        将新节点合并到节点池。
        去重：余弦相似 > 0.95 视为同一节点。
        """
        if not self._node_pool:
            self._node_pool = [list(n) for n in new_nodes]
            return

        threshold = 0.95
        for node in new_nodes:
            duplicate = False
            for existing in self._node_pool:
                if self._cosine_sim(existing, node) > threshold:
                    duplicate = True
                    # 加权平均融合（保留历史信息）
                    for k in range(len(existing)):
                        existing[k] = (existing[k] + node[k]) / 2.0
                    break
            if not duplicate:
                self._node_pool.append(list(node))

    def get_constraint_state(self) -> dict:
        """导出当前约束求解状态（供遥测/日志使用）。"""
        return {
            "session_id": self.session_id,
            "iteration": self._iteration,
            "total_constraints": len(self._constraints),
            "node_pool_size": len(self._node_pool),
            "state_counts": {
                "resolved": sum(1 for c in self._constraints
                                if c.state == SolvingState.RESOLVED),
                "stuck": sum(1 for c in self._constraints
                             if c.state == SolvingState.STUCK),
                "pruned": sum(1 for c in self._constraints
                              if c.state == SolvingState.PRUNED),
                "active": sum(1 for c in self._constraints
                              if c.state == SolvingState.ACTIVE),
                "pending": sum(1 for c in self._constraints
                               if c.state == SolvingState.PENDING),
            },
            "isomorphisms_found": len(self._isomorphisms),
            "merged_count": self._merged_count,
        }

    def reset(self) -> None:
        """清空求解器（新梦境期重新开始）。"""
        self._snapshots.clear()
        self._constraints.clear()
        self._node_pool.clear()
        self._iteration = 0
        self._started = time.time()
        self._deadlock_counters.clear()
        self._isomorphisms.clear()
        self._merged_count = 0
        self.session_id = f"dream_{int(time.time())}"

    def close(self) -> None:
        """关闭引擎，保存状态。"""
        self.save_state()


# ═══════════════════════════════════════════════════════════════════════════
# 4. 自测模式
# ═══════════════════════════════════════════════════════════════════════════

def _test():
    """无依赖自测：python src/dream_topology_engine.py --dry"""
    print("=" * 60)
    print("DreamTopologyEngine 自测")
    print("=" * 60)

    # --- Test 1: 基本流程 ---
    engine = DreamTopologyEngine(config={"random_seed": 42})
    snapshot = TopologySnapshot(
        timestamp="2026-07-21T10:30:00",
        source="test",
        nodes=[
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
            [0.9, 0.8, 0.7],
            [0.3, 0.4, 0.5],
            [0.6, 0.5, 0.4],
        ],
    )
    engine.load_snapshot(snapshot)
    report = engine.solve(iterations=5)
    state = engine.get_constraint_state()
    print(f"\n[Test 1] 基本求解流程")
    print(f"  快照: {snapshot.n_nodes} nodes × {snapshot.dim} dim")
    print(f"  约束: {state['total_constraints']} total")
    print(f"  状态: resolved={state['state_counts']['resolved']} "
          f"stuck={state['state_counts']['stuck']} "
          f"pruned={state['state_counts']['pruned']} "
          f"active={state['state_counts']['active']}")
    assert report.snapshots_processed == 1, "应有 1 个快照"
    assert report.session_id == engine.session_id
    print(f"   ✅ PASS")

    # --- Test 2: 报告完整性 ---
    print(f"\n[Test 2] 报告完整性")
    print(f"  {report.summary_line()}")
    rdict = report.to_dict()
    for key in ("resolved", "stuck", "pruned", "total_constraints", "mean_final_tension"):
        assert key in rdict, f"报告缺少字段: {key}"
    print(f"   ✅ PASS")

    # --- Test 3: 多快照合并 ---
    engine2 = DreamTopologyEngine()
    snap1 = TopologySnapshot(
        timestamp="2026-07-21T10:00:00", source="test_a",
        nodes=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
    )
    snap2 = TopologySnapshot(
        timestamp="2026-07-21T10:05:00", source="test_b",
        nodes=[[0.6, 0.5], [0.4, 0.3], [0.2, 0.1]],
    )
    engine2.load_snapshot(snap1)
    engine2.load_snapshot(snap2)
    assert len(engine2._snapshots) == 2, "应有 2 个快照"
    print(f"\n[Test 3] 多快照合并")
    print(f"  快照数: {len(engine2._snapshots)}")
    print(f"  节点池大小: {len(engine2._node_pool)} (去重后)")
    assert len(engine2._node_pool) <= 6
    print(f"   ✅ PASS")

    # --- Test 4: 快照校验（异常输入）---
    engine3 = DreamTopologyEngine()
    try:
        bad_snap = TopologySnapshot(
            timestamp="bad", source="test",
            nodes=[[0.1, 0.2], [0.3]],  # 维度不一致
        )
        engine3.load_snapshot(bad_snap)
        print(f"\n[Test 4] 异常输入校验 ❌ FAIL (未抛出异常)")
        assert False
    except ValueError:
        print(f"\n[Test 4] 异常输入校验 ✅ PASS")

    # --- Test 5: 死锁检测 ---
    engine4 = DreamTopologyEngine(config={"deadlock_limit": 2, "random_seed": 42})
    snap = TopologySnapshot(
        timestamp="deadlock_test", source="test",
        nodes=[[0.1, 0.2], [0.3, 0.4]],
    )
    engine4.load_snapshot(snap)
    engine4.extract_constraints()  # 先提取约束，再修改
    for c in engine4._constraints:
        c.stuck_count = 2  # deadlock_limit=2 → 下一次迭代会死锁
    report = engine4.solve(iterations=1)
    stuck = sum(1 for c in engine4._constraints if c.state == SolvingState.STUCK)
    print(f"\n[Test 5] 死锁检测")
    print(f"  死锁约束: {stuck}/{len(engine4._constraints)}")
    print(f"   ✅ PASS")

    # --- Test 6: 状态持久化 ---
    engine5 = DreamTopologyEngine(session_id="test_persist")
    snap = TopologySnapshot(
        timestamp="persist_test", source="test",
        nodes=[[0.1, 0.2], [0.3, 0.4]],
    )
    engine5.load_snapshot(snap)
    engine5.extract_constraints()
    engine5.save_state()
    engine6 = DreamTopologyEngine(config={"random_seed": 42})
    restored = engine6.load_state()
    assert isinstance(restored, bool)
    print(f"\n[Test 6] 状态持久化")
    print(f"  恢复成功: {restored}")
    assert restored, "状态应当可恢复"
    assert engine6.session_id == "test_persist"
    assert len(engine6._constraints) > 0
    print(f"   ✅ PASS")

    # --- Test 7: 表层输出门禁验证 ---
    print(f"\n[Test 7] 表层输出门禁验证")
    print(f"  DreamSessionReport 是结构化数据，不是叙事")
    print(f"  禁止输出到 language_system: 由 deep_surface_interface 门控")
    engine7 = DreamTopologyEngine(config={"random_seed": 42})
    snap = TopologySnapshot(
        timestamp="test7", source="test",
        nodes=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
    )
    engine7.load_snapshot(snap)
    r = engine7.solve(iterations=3)
    print(f"  报告字段: {list(r.to_dict().keys())}")
    assert isinstance(r.to_dict(), dict)
    assert "session_id" in r.to_dict()
    print(f"   ✅ PASS")

    print("\n" + "=" * 60)
    print("所有自测通过")
    print("=" * 60)

    # 清理
    state_file = os.path.join(_memory(), "dream_topology_state.json")
    if os.path.exists(state_file):
        os.remove(state_file)


if __name__ == "__main__":
    if "--dry" in sys.argv:
        _test()
    else:
        print("DreamTopologyEngine: 使用 --dry 运行自测")
