# -*- coding: utf-8 -*-
"""
seal_graph.py — 锚点交互图 + 拓扑密度计算

C→A 前置：把"钢印密度"从孤立计数升级为图拓扑属性。

数据来源：
  - memory/anchors.json          — 7 个孤立锚点
  - memory/seal_sensor_feed.jsonl — 61 条 seal 事件，含父子链关系
  - secure_vault/index.json        — 铸印记录

图的边：
  1. 共享 seal_id（共同封印的锚点）
  2. 父子 seal 链（同一条铸印链上的锚点）
  3. 同源锚点（同一铸印会话产生）

密度指标：
  - seal_graph_density: E / (V*(V-1)/2)  — 实际边数 / 最大边数
  - avg_seal_degree: 2E/V                 — 平均度数
  - chain_depth_score: Σdepth(anchor)    — seal 链深度积分
  - isolation_ratio: 孤立锚点数 / V
"""
from __future__ import annotations

import json
import sys
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Set, Tuple, Optional

logger = logging.getLogger("seal_graph")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ── 路径 ──────────────────────────────────────────────────────
def _ws() -> Path:
    import os
    return Path(os.environ.get("QCLAW_WORKSPACE", r"C:\Users\qq366410837\.qclaw\workspace"))

ANCHORS_FILE  = lambda: _ws() / "memory" / "anchors.json"
SEAL_FEED    = lambda: _ws() / "memory" / "seal_sensor_feed.jsonl"
ANCHORS_OUT  = lambda: _ws() / "memory" / "anchors_with_graph.json"
GRAPH_OUT    = lambda: _ws() / "_agent_memory" / "seal_graph_metrics.json"


# ── 边构建 ────────────────────────────────────────────────────
def build_seal_graph() -> Tuple[Dict[str, Dict], Dict[str, Set[str]], Dict[str, Any]]:
    """
    从 seal_sensor_feed.jsonl 抽取父子链，构建锚点交互图。

    返回：
      node_attrs: {anchor_id: {"seal_ids":[...], "degree":int, "depth":int, "isolated":bool}}
      edges: {anchor_id: {related_anchor_ids}}
      stats: {V, E, avg_degree, density, chain_depth_score, isolation_ratio}
    """
    # 1. 加载锚点
    anchors_data = json.loads(ANCHORS_FILE().read_text(encoding="utf-8", errors="ignore"))
    anchor_list: List[Dict] = anchors_data.get("anchors", [])
    anchor_by_id: Dict[str, Dict] = {a["anchor_id"]: a for a in anchor_list}

    # 2. 加载 seal 链
    try:
        raw = SEAL_FEED().read_text(encoding="utf-8", errors="ignore").strip()
        seal_events = [json.loads(l) for l in raw.splitlines() if l.strip()]
    except Exception as e:
        logger.warning(f"Seal feed read failed: {e}")
        seal_events = []

    # 3. 构建 seal -> anchor_ids 反向索引（共享 seal 的锚点）
    seal_to_anchors: Dict[str, Set[str]] = defaultdict(set)
    for a in anchor_list:
        for sid in a.get("seal_ids", []):
            seal_to_anchors[sid].add(a["anchor_id"])

    # 4. 构建 seal 父子链
    parent_map: Dict[str, str] = {}   # child -> parent
    for e in seal_events:
        sid = e.get("seal_id", "")
        pid = e.get("parent_seal_id", "")
        if pid:
            parent_map[sid] = pid

    # 5. 构建 seal 链 -> anchor 传播
    #    seal A 的祖先链上所有 seal 对应的 anchor 共享同一个"铸印会话"
    #    合并：共享同一 seal 链根的锚点算同源
    seal_chain_root: Dict[str, str] = {}
    for sid in parent_map:
        chain = []
        cur = sid
        visited = set()
        while cur in parent_map and cur not in visited:
            chain.append(cur)
            visited.add(cur)
            cur = parent_map[cur]
        if cur not in visited:
            chain.append(cur)
        seal_chain_root[sid] = cur  # 根 seal

    chain_to_anchors: Dict[str, Set[str]] = defaultdict(set)
    for sid, root in seal_chain_root.items():
        for aid in seal_to_anchors.get(sid, []):
            chain_to_anchors[root].add(aid)

    # 6. 建边
    edges: Dict[str, Set[str]] = defaultdict(set)

    # 类型1：共享 seal_id
    for sid, aids in seal_to_anchors.items():
        aids = list(aids)
        for i in range(len(aids)):
            for j in range(i + 1, len(aids)):
                edges[aids[i]].add(aids[j])
                edges[aids[j]].add(aids[i])

    # 类型2：同链锚点（共享 seal 链根）
    for root, aids in chain_to_anchors.items():
        aids = list(aids)
        for i in range(len(aids)):
            for j in range(i + 1, len(aids)):
                edges[aids[i]].add(aids[j])
                edges[aids[j]].add(aids[i])

    # 7. 计算每个锚点的属性
    node_attrs: Dict[str, Dict] = {}
    for a in anchor_list:
        aid = a["anchor_id"]
        degree = len(edges.get(aid, set()))
        # 计算 seal 链深度（沿父链向上走多远）
        depth = 0
        for sid in a.get("seal_ids", []):
            if sid in seal_chain_root:
                # 沿父链计数
                cur = sid
                d = 0
                visited = set()
                while cur in parent_map and cur not in visited:
                    d += 1
                    visited.add(cur)
                    cur = parent_map[cur]
                depth = max(depth, d)
        node_attrs[aid] = {
            "seal_ids": a.get("seal_ids", []),
            "degree": degree,
            "depth": depth,
            "isolated": degree == 0,
            "chain_roots": list(set(seal_chain_root.get(s, "") for s in a.get("seal_ids", []) if s in seal_chain_root)),
        }

    # 8. 统计
    V = len(anchor_list)
    E = sum(len(s) for s in edges.values()) // 2  # 无向边
    max_E = V * (V - 1) // 2 if V > 1 else 1
    density = E / max_E if max_E > 0 else 0.0
    avg_degree = (2 * E) / V if V > 0 else 0.0
    chain_depth_score = sum(node_attrs[a["anchor_id"]]["depth"] for a in anchor_list)
    isolated = sum(1 for a in anchor_list if node_attrs[a["anchor_id"]]["isolated"])

    stats = {
        "V": V,
        "E": E,
        "max_E": max_E,
        "density": round(density, 4),
        "avg_degree": round(avg_degree, 4),
        "chain_depth_score": chain_depth_score,
        "isolated_count": isolated,
        "isolation_ratio": round(isolated / V, 4) if V > 0 else 1.0,
        "total_seals": len(seal_to_anchors),
        "seal_chains": len(set(seal_chain_root.values())),
        "sealed_anchors": sum(1 for a in anchor_list if a.get("seal_ids")),
    }

    # 9. 构建拓扑密度（每个锚点）
    # 公式：density_per_anchor = local_degree / (V-1)
    #      weighted_density = (1/degree_weight) 基于 depth 和 shared_seal
    for aid in node_attrs:
        na = node_attrs[aid]
        na["topology_density"] = round(na["degree"] / max(V - 1, 1), 4)
        # 综合分数：度数贡献 + 链深度贡献
        na["steel_density_score"] = round(
            na["topology_density"] * 0.6 + min(na["depth"] / 5.0, 1.0) * 0.4,
            4
        )

    return node_attrs, dict(edges), stats


# ── 持久化 ────────────────────────────────────────────────────
def compute_and_save() -> Dict[str, Any]:
    """
    主入口：计算图指标，保存到文件。
    返回 stats 字典。
    """
    node_attrs, edges, stats = build_seal_graph()

    # 保存图指标
    graph_metrics = {
        "computed_at": _now_iso(),
        "source_files": {
            "anchors": str(ANCHORS_FILE()),
            "seal_feed": str(SEAL_FEED()),
        },
        "stats": stats,
        "edges": {aid: sorted(list(neighbors)) for aid, neighbors in edges.items()},
    }
    GRAPH_OUT().parent.mkdir(exist_ok=True)
    GRAPH_OUT().write_text(
        json.dumps(graph_metrics, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 增强锚点文件（追加拓扑字段，不改原有结构）
    anchors_data = json.loads(ANCHORS_FILE().read_text(encoding="utf-8", errors="ignore"))
    anchor_list: List[Dict] = anchors_data.get("anchors", [])
    for a in anchor_list:
        aid = a["anchor_id"]
        if aid in node_attrs:
            na = node_attrs[aid]
            # 追加字段（不删除原有字段）
            a["topology"] = {
                "degree": na["degree"],
                "depth": na["depth"],
                "isolated": na["isolated"],
                "topology_density": na["topology_density"],
                "steel_density_score": na["steel_density_score"],
                "chain_roots": na["chain_roots"],
            }

    enhanced = {
        "anchors": anchor_list,
        "timestamp": anchors_data.get("timestamp", ""),
        "graph_computed_at": _now_iso(),
        "graph_stats": stats,
    }
    ANCHORS_OUT().write_text(
        json.dumps(enhanced, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return stats


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if args.run or args.stats:
        stats = compute_and_save()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        print()
        print("Files written:")
        print("  ", GRAPH_OUT())
        print("  ", ANCHORS_OUT())
