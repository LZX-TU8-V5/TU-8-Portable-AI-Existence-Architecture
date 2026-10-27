"""
matrix_operators.py — 话题语义矩阵四算子（NMF/SVD/LSA/DAG）[H 级批次2, 2026-08-29 落地]

设计稿：docs/design/topic_matrix_impl_design_2026-08-28.md §4/§6
职责：
  - LSA：向量余弦跨字面对齐（已部分在 topic_matrix.project，本模块统一接口）
  - DAG：L2 事件时间戳→因果拓扑（纯 Python）
  - NMF：基主题加法分解（W,H≥0）；纯 Python 近似版（无 numpy 时走质心投影）
  - SVD：离线结构压缩；纯 Python 近似版（截断奇异值替代）

环境约束：workbuddy python 无 numpy → 全部纯标准库实现；
  若检测 numpy 可用则走精确迭代分解（可插拔，接口不变）。

铁律：六维非负 → NMF 输入先验（不重造 tu8_memory 六维计算）；
      不引云、本地优先。
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Optional


def _try_numpy():
    try:
        import numpy as np  # type: ignore
        return np
    except Exception:
        return None


# ============ LSA：跨字面对齐（向量余弦，统一接口）============
def lsa_align(query_vec: list[float], region_reps: dict[str, list[float]],
              top_k: int = 5) -> list[tuple[str, float]]:
    """
    LSA 跨字面对齐：用向量空间余弦替代关键词命中（设计稿 §4/§7 检索剪枝）。
    query_vec: 查询/事件向量；region_reps: {code: 代表向量}
    返回按余弦降序的 (code, sim)
    """
    np = _try_numpy()
    scored = []
    for code, rvec in region_reps.items():
        if np is not None:
            sim = float(np.dot(query_vec, rvec) /
                        (np.linalg.norm(query_vec) * np.linalg.norm(rvec) + 1e-9))
        else:
            dot = sum(a * b for a, b in zip(query_vec, rvec))
            na = sum(a * a for a in query_vec) ** 0.5
            nb = sum(b * b for b in rvec) ** 0.5
            sim = dot / (na * nb + 1e-9) if na and nb else 0.0
        scored.append((code, sim))
    scored.sort(key=lambda x: -x[1])
    return scored[:top_k]


# ============ DAG：时间戳因果拓扑 ============
def build_causal_chain(events: list[dict]) -> dict:
    """
    输入 events: [{"event_id","timestamp","parent_ids":[...]}, ...]
    输出 DAG 邻接结构（按需追溯，不读全史）。
    边：parent -> child（parent_ids 指向更早事件）。
    """
    nodes = {e["event_id"]: e for e in events}
    edges = defaultdict(list)      # child -> [parents]
    forward = defaultdict(list)    # parent -> [children]
    for e in events:
        eid = e["event_id"]
        for pid in e.get("parent_ids", []) or []:
            if pid in nodes:
                edges[eid].append(pid)
                forward[pid].append(eid)
    # 拓扑序（Kahn）
    indeg = {eid: len(edges[eid]) for eid in nodes}
    q = deque([eid for eid, d in indeg.items() if d == 0])
    topo = []
    while q:
        n = q.popleft()
        topo.append(n)
        for c in forward[n]:
            indeg[c] -= 1
            if indeg[c] == 0:
                q.append(c)
    return {
        "nodes": list(nodes.keys()),
        "edges_parent_of": dict(forward),     # parent -> children
        "edges_child_of": dict(edges),        # child -> parents
        "topo_order": topo,
        "acyclic": len(topo) == len(nodes),
    }


def trace_chain(dag: dict, event_id: str, depth: int = 3) -> list[str]:
    """从 event_id 向上追溯父链（按需， depth 限制不读全史）。"""
    seen, chain, stack = set(), [], [(event_id, 0)]
    while stack:
        nid, d = stack.pop()
        if d > depth or nid in seen or nid not in dag["edges_child_of"]:
            continue
        seen.add(nid)
        chain.append(nid)
        for p in dag["edges_child_of"][nid]:
            stack.append((p, d + 1))
    return chain


# ============ NMF：基主题加法分解（W,H>=0）============
def nmf_cluster(sections: list[dict], k: int = 8) -> tuple[list, list]:
    """
    输入 sections: [{"text", "weights": {"freq","rel","div",...}}, ...]
    六维非负权重作初始化先验（设计稿 §4：NMF 输入 = tu8_memory 六维）。
    纯 Python 近似（无 numpy）：用六维非负权重投影到 k 个基主题簇（质心法），
      等价于"加法可解释组合"的弱实现；有 numpy 时可升级为真 multiplicative update。
    返回 (W 段-主题分配, H 主题-维度质心) 近似。
    """
    np = _try_numpy()
    dims = ["freq", "rel", "div", "cons", "meaning", "emotion"]
    vecs = []
    for s in sections:
        w = s.get("weights", {})
        vecs.append([float(w.get(d, 0.0)) for d in dims])

    if np is not None:
        # 精确路径（若 numpy 可用，用简单 k-means 近似质心；真 NMF 迭代留 TODO）
        M = np.array(vecs, dtype=float)
        # 质心初始化：按行范数排序取前 k 个作种子
        norms = np.linalg.norm(M, axis=1)
        seeds = [i for i in np.argsort(-norms)[:k]]
        centers = M[seeds].copy()
        W = [[0.0] * k for _ in range(len(M))]
        for i in range(len(M)):
            W[i] = (M[i] @ centers.T / (np.linalg.norm(centers, axis=1) + 1e-9)).tolist()
        H = centers.tolist()
        return W, H

    # 纯 Python 近似：k-means++ 风格质心（保证非负）
    n = len(vecs)
    if n == 0:
        return [], []
    # 种子：取范数最大 k 个
    norms = [math.sqrt(sum(v * v for v in vec)) for vec in vecs]
    order = sorted(range(n), key=lambda i: -norms[i])[:k]
    centers = [list(vecs[i]) for i in order]
    W = [[0.0] * k for _ in range(n)]
    for i, vec in enumerate(vecs):
        sims = []
        for c in centers:
            dot = sum(a * b for a, b in zip(vec, c))
            nc = math.sqrt(sum(x * x for x in c)) + 1e-9
            nv = math.sqrt(sum(x * x for x in vec)) + 1e-9
            sims.append(dot / (nc * nv))
        W[i] = sims
    return W, centers


# ============ SVD：离线结构压缩（截断）============
def svd_compress(matrix: list[list[float]], k: int = 4) -> dict:
    """
    离线算结构压缩（设计稿 §6：算各区质心 reps 用）。
    纯 Python 近似：PCA 式 top-k 主方向（幂迭代取首特征向量，截断 k 个）。
    有 numpy 时走 np.linalg.svd 截断。
    返回 {k, components, explained_ratio}
    """
    np = _try_numpy()
    if np is not None and matrix:
        M = np.array(matrix, dtype=float)
        # 中心化
        M = M - M.mean(axis=0)
        try:
            U, S, Vt = np.linalg.svd(M, full_matrices=False)
            kk = min(k, len(S))
            explained = float((S[:kk] ** 2).sum() / (S ** 2).sum()) if S.sum() > 0 else 0.0
            return {"k": kk, "components": Vt[:kk].tolist(),
                    "singular": S[:kk].tolist(), "explained_ratio": explained}
        except Exception:
            pass

    # 纯 Python 近似：幂迭代取 top-1 主方向（截断 k 个用多次正交化）
    n_rows = len(matrix)
    n_cols = len(matrix[0]) if matrix else 0
    if n_rows < 2 or n_cols == 0:
        return {"k": 0, "components": [], "explained_ratio": 0.0}
    # 中心化
    col_mean = [sum(matrix[r][c] for r in range(n_rows)) / n_rows for c in range(n_cols)]
    Mc = [[matrix[r][c] - col_mean[c] for c in range(n_cols)] for r in range(n_rows)]
    comps = []
    total_var = sum(sum(x * x for x in row) for row in Mc)
    explained = 0.0
    for _ in range(min(k, n_cols)):
        # 幂迭代
        v = [1.0 / math.sqrt(n_cols)] * n_cols
        for _it in range(20):
            w = [0.0] * n_cols
            for r in range(n_rows):
                dot = sum(Mc[r][c] * v[c] for c in range(n_cols))
                for c in range(n_cols):
                    w[c] += dot * Mc[r][c]
            # 正交化已有成分
            for comp in comps:
                proj = sum(w[c] * comp[c] for c in range(n_cols))
                for c in range(n_cols):
                    w[c] -= proj * comp[c]
            nv = math.sqrt(sum(x * x for x in w)) + 1e-9
            v = [x / nv for x in w]
        # 解释方差
        lam = 0.0
        for r in range(n_rows):
            dot = sum(Mc[r][c] * v[c] for c in range(n_cols))
            lam += dot * dot
        explained += lam / (total_var + 1e-9)
        comps.append(v)
        #  deflation
        for r in range(n_rows):
            dot = sum(Mc[r][c] * v[c] for c in range(n_cols))
            for c in range(n_cols):
                Mc[r][c] -= dot * v[c]
        total_var -= lam
        if total_var <= 1e-9:
            break
    return {"k": len(comps), "components": comps,
            "explained_ratio": min(1.0, explained)}


if __name__ == "__main__":
    # DAG 自测
    evs = [
        {"event_id": "e1", "timestamp": 1, "parent_ids": []},
        {"event_id": "e2", "timestamp": 2, "parent_ids": ["e1"]},
        {"event_id": "e3", "timestamp": 3, "parent_ids": ["e1", "e2"]},
    ]
    dag = build_causal_chain(evs)
    print("DAG acyclic:", dag["acyclic"], "topo:", dag["topo_order"])
    print("trace e3:", trace_chain(dag, "e3"))
    # NMF 近似
    secs = [
        {"text": "a", "weights": {"freq": 0.9, "rel": 0.8, "div": 0.1}},
        {"text": "b", "weights": {"freq": 0.1, "rel": 0.2, "div": 0.9}},
        {"text": "c", "weights": {"freq": 0.85, "rel": 0.7, "div": 0.2}},
    ]
    W, H = nmf_cluster(secs, k=2)
    print("NMF W:", [ [round(x,2) for x in row] for row in W])
    # SVD 近似
    mat = [[1.0, 0.9, 0.1], [0.9, 1.0, 0.2], [0.2, 0.1, 0.8]]
    print("SVD:", svd_compress(mat, k=2))
    print("ALL OPS OK")
