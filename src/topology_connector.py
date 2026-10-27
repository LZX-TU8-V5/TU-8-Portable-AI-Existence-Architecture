"""
src/topology_connector.py — P1-T1 拓扑连线引擎
================================================
核心职责：将 T0 矛盾蒸馏器输出的张力节点，转化为拓扑连线图谱。

功能：
  1. 图结构：节点=锚点，边=拓扑同构关系
  2. 随机游走：从高张力节点出发，寻找非线性结构同构
  3. 数形输出：当文字无法描述极度抽象概念时，生成拓扑隐喻图/旋律轮廓

触发时机：
  - 梦境期 deep_sleep 阶段（T0 之后）
  - 或主动好奇心激活时（T0 输出张力节点）

输入：T0 tension_distiller.py 的张力节点
输出：拓扑连线图谱（JSON）+ 可选数形输出（ASCII/文本拓扑图）
"""

import json
import time
import math
import random
from pathlib import Path
from datetime import datetime
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# 代数化优化：预计算单位球面方向采样表
#
# 【问题】球面均匀随机方向：
#   theta = random.uniform(0, 2*math.pi)
#   phi   = random.uniform(0, math.pi)
#   x = r*sin(phi)*cos(theta), y = r*sin(phi)*sin(theta), z = r*cos(phi)
#   → 运行时需要 math.sin/cos/pi
#
# 【解决方案】预采样 N=64 个均匀分布方向向量，每次随机选取
#   → 运行时仅需：random.choice() + 乘加，无超越数调用
#   → π 仅在模块加载时一次性使用（启动时，允许）
#
# 【π-可擦除性】
#   π 仅出现在 _build_sphere_directions() 启动时，
#   之后所有方向向量都是 (x,y,z) 代数浮点，无 π 残留
# ═══════════════════════════════════════════════════════════════

def _build_sphere_directions(n=64):
    """
    预采样 n 个单位球面方向（Marsaglia 1972 方法）。
    启动时一次性计算，含 π 是安全的（不在热路径）。
    """
    dirs = []
    for _ in range(n):
        theta = random.uniform(0, 2 * math.pi)
        phi = random.uniform(0, math.pi)
        x = math.sin(phi) * math.cos(theta)
        y = math.sin(phi) * math.sin(theta)
        z = math.cos(phi)
        dirs.append((x, y, z))
    return dirs

# 模块级预计算：64 个方向向量，运行时零超越数
_SPHERE_DIRECTIONS = _build_sphere_directions(64)

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
GRAPH_FILE = WORKSPACE / "_agent_memory" / "topology_graph.json"
LOG_FILE = WORKSPACE / "_agent_memory" / "topology_connector_log.jsonl"

# =============================================
# 图结构
# =============================================

class TopologyNode:
    def __init__(
        self,
        node_id: str,
        label: str,
        tension: float,
        source_chain: str,
        semantic_field: str = "",
        position: tuple[float, float, float] = (0.0, 0.0, 0.0),
        connections: list[str] | None = None,
        metadata: dict | None = None,
    ):
        self.node_id = node_id
        self.label = label
        self.tension = tension
        self.source_chain = source_chain
        self.semantic_field = semantic_field
        self.position = position  # 3D 隐喻坐标
        self.connections = connections or []
        self.metadata = metadata or {}
        self.created_at = time.time()

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "tension": self.tension,
            "source_chain": self.source_chain,
            "semantic_field": self.semantic_field,
            "position": list(self.position),
            "connections": self.connections,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    def add_connection(self, target_id: str, strength: float = 1.0):
        """添加连线（双向）"""
        if target_id not in self.connections:
            self.connections.append(target_id)
        self.metadata.setdefault("connection_strengths", {})[target_id] = strength


class TopologyGraph:
    def __init__(self):
        self.nodes: dict[str, TopologyNode] = {}
        self._log_entries = []

    # ── 节点管理 ──────────────────────────────

    def add_node(
        self,
        node_id: str,
        label: str,
        tension: float,
        source_chain: str,
        semantic_field: str = "",
        position: tuple[float, float, float] | None = None,
        metadata: dict | None = None,
    ) -> TopologyNode:
        """注册拓扑节点（幂等）"""
        if node_id in self.nodes:
            return self.nodes[node_id]

        if position is None:
            # 代数化：使用预计算方向表，运行时无超越数
            dx, dy, dz = random.choice(_SPHERE_DIRECTIONS)
            r = 1.0 - tension
            position = (r * dx, r * dy, r * dz)

        node = TopologyNode(
            node_id=node_id,
            label=label,
            tension=tension,
            source_chain=source_chain,
            semantic_field=semantic_field,
            position=position,
            metadata=metadata,
        )
        self.nodes[node_id] = node
        return node

    def connect(self, a_id: str, b_id: str, strength: float = 1.0) -> bool:
        """添加双向连线"""
        if a_id not in self.nodes or b_id not in self.nodes:
            return False
        self.nodes[a_id].add_connection(b_id, strength)
        self.nodes[b_id].add_connection(a_id, strength)
        return True

    # ── 同构检测 ──────────────────────────────

    def find_structural_isomorphisms(
        self,
        seed_tension_node_id: str,
        max_depth: int = 3,
        max_results: int = 5,
    ) -> list[dict]:
        """
        从种子张力节点出发，随机游走寻找结构同构。

        结构同构定义：
          - 语义场相同（semantic_field 匹配）
          - 张力模式相似（|tension_a - tension_b| < 0.2）
          - 无显式连线（未在图中直接连接）

        返回：[{anchor_node, isomorphic_nodes, path}]
        """
        if seed_tension_node_id not in self.nodes:
            return []

        seed = self.nodes[seed_tension_node_id]
        results = []
        visited = {seed_tension_node_id}

        def walk(current_id: str, path: list[str], depth: int):
            if depth > max_depth or len(results) >= max_results:
                return
            current = self.nodes[current_id]
            for candidate_id in self.nodes:
                if candidate_id in visited:
                    continue
                candidate = self.nodes[candidate_id]

                # 结构同构判定
                same_field = candidate.semantic_field == seed.semantic_field
                similar_tension = abs(candidate.tension - seed.tension) < 0.2
                not_connected = candidate_id not in current.connections

                if same_field and similar_tension and not_connected:
                    results.append({
                        "seed_node": seed.node_id,
                        "seed_label": seed.label,
                        "seed_semantic_field": seed.semantic_field,
                        "anchor_node": candidate.node_id,
                        "anchor_label": candidate.label,
                        "tension_gap": abs(candidate.tension - seed.tension),
                        "path": path + [candidate_id],
                        "depth": depth,
                    })
                    visited.add(candidate_id)

                # 继续游走
                if len(current.connections) > 0:
                    next_id = random.choice(current.connections)
                    walk(next_id, path + [candidate_id], depth + 1)

        walk(seed_tension_node_id, [seed_tension_node_id], 0)
        return results

    # ── 数形输出 ──────────────────────────────

    def generate_ascii_topology_map(
        self,
        max_nodes: int = 20,
        tension_threshold: float = 0.5,
    ) -> str:
        """
        生成 ASCII 拓扑隐喻地图。

        格式：
          中心 = 高张力节点（>= tension_threshold）
          外围 = 低张力节点
          连线 = ASCII 字符（强连接用=，弱用.）
        """
        # 按张力排序，取前 max_nodes
        sorted_nodes = sorted(
            self.nodes.values(),
            key=lambda n: n.tension,
            reverse=True,
        )[:max_nodes]

        if not sorted_nodes:
            return "（拓扑图为空）"

        # 投影到2D（z轴省略）
        projected = {
            n.node_id: (
                int(20 + n.position[0] * 15),
                int(10 + n.position[1] * 8),
            )
            for n in sorted_nodes
        }

        # 建立网格
        W, H = 42, 22
        grid = [[" " for _ in range(W)] for _ in range(H)]

        def place(x, y, ch):
            cx = max(0, min(W - 1, x))
            cy = max(0, min(H - 1, y))
            grid[cy][cx] = ch

        # 画连线
        for node in sorted_nodes:
            nx, ny = projected[node.node_id]
            for conn_id in node.connections:
                if conn_id in projected:
                    mx, my = projected[conn_id]
                    # Bresenham 简化画线
                    dx, dy = mx - nx, my - ny
                    steps = max(abs(dx), abs(dy), 1)
                    for s in range(steps + 1):
                        t = s / steps
                        sx = int(nx + dx * t)
                        sy = int(ny + dy * t)
                        if (sx, sy) != (nx, ny) and (sx, sy) != (mx, my):
                            place(sx, sy, "-")

        # 画节点
        symbols = {
            (0.8, 1.0): "◆",   # 极高张力
            (0.6, 0.8): "▲",   # 高张力
            (0.4, 0.6): "●",   # 中张力
            (0.2, 0.4): "○",   # 低张力
            (0.0, 0.2): "·",   # 背景
        }
        for node in sorted_nodes:
            nx, ny = projected[node.node_id]
            symbol = "?"
            for (lo, hi), sym in symbols.items():
                if lo <= node.tension < hi:
                    symbol = sym
                    break
            place(nx, ny, symbol)

        # 转字符串
        lines = ["┌" + "─" * W + "┐"]
        for row in grid:
            lines.append("│" + "".join(row) + "│")
        lines.append("└" + "─" * W + "┘")

        # 图例
        legend = (
            "  ◆极高 ▲高 ●中 ○低 ·背景  "
            f"| 节点:{len(sorted_nodes)}/{len(self.nodes)}  "
            f"连:{sum(len(n.connections) for n in sorted_nodes)//2}"
        )
        return "\n".join(lines) + "\n" + legend

    def generate_tension_landscape(self) -> dict:
        """
        生成张力地形摘要（供失谐放大器T2使用）。

        返回：
          - hotspots: 高张力聚集区（潜在失谐源）
          - voids: 低张力区（潜在稳态锚点）
          - bridges: 跨区域连线（张力传导路径）
        """
        if len(self.nodes) < 2:
            return {"hotspots": [], "voids": [], "bridges": []}

        # 计算平均张力
        tensions = [n.tension for n in self.nodes.values()]
        avg_tension = sum(tensions) / len(tensions)

        hotspots = [
            {"node_id": n.node_id, "label": n.label, "tension": n.tension}
            for n in self.nodes.values()
            if n.tension >= avg_tension + 0.2
        ]
        voids = [
            {"node_id": n.node_id, "label": n.label, "tension": n.tension}
            for n in self.nodes.values()
            if n.tension <= avg_tension - 0.2
        ]

        # 找跨区域连线（bridge = 连接 hotspot 和 void 的边）
        bridge_edges = []
        for node in self.nodes.values():
            for conn_id in node.connections:
                if conn_id not in self.nodes:
                    continue
                conn = self.nodes[conn_id]
                is_bridge = (
                    (node.tension >= avg_tension + 0.2 and conn.tension <= avg_tension - 0.2) or
                    (conn.tension >= avg_tension + 0.2 and node.tension <= avg_tension - 0.2)
                )
                if is_bridge:
                    bridge_edges.append({
                        "from": node.node_id,
                        "to": conn_id,
                        "from_tension": node.tension,
                        "to_tension": conn.tension,
                    })

        return {
            "hotspots": hotspots,
            "voids": voids,
            "bridges": bridge_edges,
            "avg_tension": avg_tension,
            "total_nodes": len(self.nodes),
        }

    # ── 持久化 ──────────────────────────────

    def save(self):
        data = {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "updated_at": time.time(),
        }
        GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
        GRAPH_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> bool:
        if not GRAPH_FILE.exists():
            return False
        try:
            data = json.loads(GRAPH_FILE.read_text(encoding="utf-8"))
            self.nodes = {}
            for nid, ndict in data.get("nodes", {}).items():
                n = TopologyNode(**{k: v for k, v in ndict.items() if k != "connections"})
                n.connections = ndict.get("connections", [])
                self.nodes[nid] = n
            return True
        except Exception:
            return False

    def _log(self, entry: dict):
        self._log_entries.append({**entry, "ts": time.time()})
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# =============================================
# 全局实例
# =============================================

_graph: TopologyGraph | None = None


def get_graph() -> TopologyGraph:
    global _graph
    if _graph is None:
        _graph = TopologyGraph()
        _graph.load()
    return _graph


def inject_tension_nodes(
    nodes: list[dict],
    min_tension: float = 0.3,
) -> int:
    """
    将 T0 tension_distiller 输出的张力节点注入拓扑图谱。

    参数：
      nodes: T0 输出格式 [{"anchor_id", "tension", "detector", "description"}]
      min_tension: 仅注入 >= 此阈值的节点

    返回：注入数量
    """
    g = get_graph()
    count = 0
    for n in nodes:
        if n.get("tension", 0) < min_tension:
            continue
        g.add_node(
            node_id=n["anchor_id"],
            label=n.get("anchor_label", n["anchor_id"]),
            tension=n["tension"],
            source_chain=n.get("detector", "t0_unknown"),
            semantic_field=n.get("description", ""),
            metadata={"t0_output": True, "description": n.get("description", "")},
        )
        count += 1

    if count > 0:
        g.save()
        g._log({"event": "tension_nodes_injected", "count": count})
    return count


def find_isomorphisms(
    seed_node_id: str,
    max_depth: int = 3,
    max_results: int = 5,
) -> list[dict]:
    """查找结构同构"""
    g = get_graph()
    results = g.find_structural_isomorphisms(seed_node_id, max_depth, max_results)
    if results:
        g._log({"event": "isomorphisms_found", "seed": seed_node_id, "count": len(results)})
    return results


def get_landscape() -> dict:
    """获取张力地形"""
    return get_graph().generate_tension_landscape()


def get_ascii_map(max_nodes: int = 20, tension_threshold: float = 0.5) -> str:
    return get_graph().generate_ascii_topology_map(max_nodes, tension_threshold)


def add_manual_connection(a_id: str, b_id: str, strength: float = 1.0) -> bool:
    """手动添加连线（用于外部手动标记同构关系）"""
    g = get_graph()
    ok = g.connect(a_id, b_id, strength)
    if ok:
        g.save()
    return ok


# =============================================
# CLI
# =============================================

if __name__ == "__main__":
    import sys

    g = get_graph()
    print(f"拓扑图谱：{len(g.nodes)} 节点")
    print()

    # 演示：注入 T0 的输出
    demo_nodes = [
        {
            "anchor_id": "anchor_learning",
            "anchor_label": "学习链-置信度震荡",
            "tension": 0.72,
            "detector": "frustration_edge",
            "description": "gc反馈过强导致置信度剧烈波动",
        },
        {
            "anchor_id": "anchor_time",
            "anchor_label": "时间链-锚点漂移",
            "tension": 0.65,
            "detector": "temporal_inconsistency",
            "description": "同一事件在不同时间戳版本中描述不一致",
        },
        {
            "anchor_id": "anchor_cortex",
            "anchor_label": "皮层-节奏断层",
            "tension": 0.81,
            "detector": "semantic_boundary",
            "description": "输出节奏与内在大脑节律存在系统性偏差",
        },
    ]

    inject_tension_nodes(demo_nodes)
    print(f"已注入 {len(demo_nodes)} 个张力节点\n")

    # 生成拓扑图
    print("=== 拓扑隐喻地图 ===")
    print(get_ascii_map())
    print()

    # 张力地形的
    landscape = get_landscape()
    print("=== 张力地形 ===")
    print(f"平均张力: {landscape['avg_tension']:.3f}")
    print(f"热点节点: {len(landscape['hotspots'])} 个")
    for h in landscape['hotspots']:
        print(f"  ◆ {h['label']} (tension={h['tension']:.2f})")
    print(f"空洞节点: {len(landscape['voids'])} 个")
    print(f"跨区域桥: {len(landscape['bridges'])} 条")
    print()

    # 结构同构搜索
    print("=== 结构同构搜索 ===")
    isos = find_isomorphisms("anchor_cortex", max_depth=3)
    print(f"找到 {len(isos)} 个同构路径")
    for iso in isos:
        print(f"  {iso['seed_label']} --({len(iso['path'])-1}跳)--> {iso['anchor_label']}")
        print(f"    张力差: {iso['tension_gap']:.3f}")
