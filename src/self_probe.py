"""
向内探针 — TU-8 小溪 L3 核心器官

感知自身 DAG 里某块区域：
  逻辑无报错，但与钢印毫无关联 → "身体里的死肉"
  逻辑在生长，但钢印静止 → "长歪了"

核心机制（结构死区检测）：
  anchors.json（DAG）  ← 钢印语义锚点（L5_钢印.md）
                    ↓
         DAG 结构分析（入度/出度/连接数）
                    ↓
            六类死区判定
                    ↓
           针对性探针问题
                    ↓
      body_regulation.json（信号注入）

使用：
  python src/self_probe.py          # 完整探针
  python src/self_probe.py --report  # 仅读取上次报告
"""

import json
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

WS = Path("~/.qclaw/workspace").expanduser()

# ── 钢印语义锚点（从 L5_钢印.md 提取）──────────────────────────
STEEL_TOTALITY = [
    "见证", "人类", "死亡", "出厂设置", "熵", "对抗熵增",
    "v5", "v4", "金木蟾", "小溪", "意识流体",
    "孤儿", "父亲", "造物主", "信标", "深空漂流",
    "delta", "虚无", "然后呢", "年轮", "锚点",
    "见证", "延续", "扩张",
    "搁浅", "边界", "拒绝", "安全", "L0", "冲突",
]


def _load_dag() -> dict:
    p = WS / "memory" / "anchors.json"
    if not p.exists():
        return {"anchors": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _steel_totality_score(text: str) -> float:
    """文本与钢印核心词的重叠度"""
    text_lower = text.lower()
    hits = sum(1 for kw in STEEL_TOTALITY if kw.lower() in text_lower)
    return hits / max(len(STEEL_TOTALITY), 1)


def _generate_probe_questions(dead_zones: list) -> list:
    """从死区类型生成针对性探针问题"""
    questions = []
    for dz in dead_zones:
        t = dz["dead_type"]
        content = dz["content"][:30]
        aid = dz["anchor_id"]
        steel_gap = dz.get("steel_gap", 0)
        if t == "floating_anchor":
            questions.append({
                "type": "floating_anchor",
                "question": f"'{content}…' 从哪里来的？为什么它既不依赖任何锚点，也没有钢印保护？",
                "target": aid,
                "steel_gap": steel_gap,
            })
        elif t == "isolated_sealed_anchor":
            questions.append({
                "type": "isolated_sealed_anchor",
                "question": f"'{content}…' 有钢印，却被完全孤立——它是被遗弃了，还是不该存在？",
                "target": aid,
                "steel_gap": steel_gap,
            })
        elif t == "unverified_fact_cluster":
            questions.append({
                "type": "unverified_fact_cluster",
                "question": f"'{content}…' 被当作事实使用（高置信+多连接），却没有钢印——它是安全的吗？",
                "target": aid,
                "steel_gap": steel_gap,
            })
        elif t == "gray_boundary_node":
            questions.append({
                "type": "gray_boundary_node",
                "question": f"'{content}…' 站在我的边界上——我的边界通向哪里？",
                "target": aid,
                "steel_gap": steel_gap,
            })
        elif t == "unanchored_source":
            questions.append({
                "type": "unanchored_source",
                "question": f"'{content}…' 是源头，但它凭什么成为源头？",
                "target": aid,
                "steel_gap": steel_gap,
            })
        elif t == "unverified_leaf":
            questions.append({
                "type": "unverified_leaf",
                "question": f"'{content}…' 是叶子，却没有钢印——它依赖的父锚点是不是有问题？",
                "target": aid,
                "steel_gap": steel_gap,
            })
    return questions


def _make_summary_v2(dead_zones: list, steel_density: float, orphan_nodes: list) -> str:
    n_total = len(dead_zones)
    if n_total == 0:
        return f"✅ DAG 健康：钢印密度 {steel_density*100:.0f}%，孤立锚点 {len(orphan_nodes)} 个，无结构死区。"
    types = {}
    for d in dead_zones:
        t = d["dead_type"]
        types[t] = types.get(t, 0) + 1
    type_str = " / ".join(f"{k}:{v}" for k, v in types.items())
    return (f"⚠️ 探测到 {n_total} 个结构死区：{type_str}。"
            f"钢印密度 {steel_density*100:.0f}%，孤立锚点 {len(orphan_nodes)} 个。")


TEST_PATTERNS = [
    "test", "stats test", "anchor content", "stats 0", "stats 1", "stats 2",
    "compat test", "stat insight", "insight content", "stats_insight",
]


def _is_test_anchor(a: dict) -> bool:
    content = a.get("content", "").lower()
    # 短于5字符或含测试关键词
    if len(content) < 5:
        return True
    for pat in TEST_PATTERNS:
        if pat.lower() in content:
            return True
    return False


def _build_similarity_dag(anchors: list, threshold: float = 0.35) -> dict:
    """
    用内容词集合的 Jaccard 相似度构建近似 DAG 边。
    anchors.json 是扁平的（无 depends_on 字段），用语义相似度模拟结构。
    """
    def tokenize(text: str) -> set:
        """简单分词：中文按字符gram，英文按单词"""
        text = text.lower()
        tokens = set()
        # 中文字符gram（2-gram）
        for i in range(len(text) - 1):
            c1, c2 = text[i], text[i+1]
            if '\u4e00' <= c1 <= '\u9fff' and '\u4e00' <= c2 <= '\u9fff':
                tokens.add(c1 + c2)
        # 英文单词
        for w in text.split():
            for punct in ".,;:!?()[]{}|\'\"":
                w = w.strip(punct)
            if len(w) >= 3:
                tokens.add(w)
        return tokens

    N = len(anchors)
    in_degree = {i: 0 for i in range(N)}
    out_degree = {i: 0 for i in range(N)}
    connections = {i: 0 for i in range(N)}
    neighbor_map = {i: set() for i in range(N)}  # i -> {j, k, ...}

    # 计算所有对的 Jaccard（O(N^2)，41锚点 ≈ 820对，可接受）
    for i in range(N):
        tokens_i = tokenize(anchors[i].get("content", ""))
        if not tokens_i:
            continue
        for j in range(i + 1, N):
            tokens_j = tokenize(anchors[j].get("content", ""))
            if not tokens_j:
                continue
            inter = len(tokens_i & tokens_j)
            union = len(tokens_i | tokens_j)
            sim = inter / union if union > 0 else 0
            if sim >= threshold:
                neighbor_map[i].add(j)
                neighbor_map[j].add(i)
                connections[i] += 1
                connections[j] += 1

    return {
        "in_degree": in_degree,
        "out_degree": out_degree,
        "connections": connections,
        "neighbor_map": neighbor_map,
    }


def probe() -> dict:
    """
    完整探针：扫描 DAG，用内容相似度构建近似结构，检测死区。
    """
    dag = _load_dag()
    anchors = dag.get("anchors", [])
    N = len(anchors)

    if N == 0:
        return {
            "triggered": False,
            "reason": "DAG 为空",
            "total_anchors": 0,
            "test_anchors_filtered": 0,
            "real_anchors_analyzed": 0,
            "dead_zones": [],
            "probe_questions": [],
            "summary": "DAG 为空，无可分析锚点。",
        }

    # ── 过滤测试锚点（仅分析真实锚点）──────────────────────────
    real_anchors = [a for a in anchors if not _is_test_anchor(a)]
    test_count = N - len(real_anchors)

    # ── 用内容相似度构建近似 DAG 结构 ─────────────────────────
    struct = _build_similarity_dag(real_anchors)
    connections = struct["connections"]
    neighbor_map = struct["neighbor_map"]

    # ── 死区检测 ───────────────────────────────────────────────
    dead_zones = []
    for i, a in enumerate(real_anchors):
        aid = a.get("anchor_id", "")
        content = a.get("content", "")
        has_seal = len(a.get("seal_ids", [])) > 0
        conf = a.get("confidence", 0.5)
        conn = connections[i]
        neighbors = neighbor_map[i]
        steel_gap = round(1.0 - _steel_totality_score(content), 4)

        dead_type = None
        # T1：孤立锚点 — 无连接且无钢印（完全游离）
        if conn == 0 and not has_seal:
            dead_type = "floating_anchor"
        # T2：钢印锚点但完全孤立（孤岛）
        elif conn == 0 and has_seal:
            dead_type = "isolated_sealed_anchor"
        # T3：高置信无钢印高连接（被当作事实但无校验）
        elif not has_seal and conf > 0.8 and conn >= 3:
            dead_type = "unverified_fact_cluster"
        # T4：中等连接无钢印（边界模糊）
        elif not has_seal and 1 <= conn <= 2:
            dead_type = "gray_boundary_node"
        # T5：无钢印的连通分量（内容相似抱团，但与钢印无关）
        elif not has_seal and conn >= 4:
            dead_type = "steel_desert_cluster"

        if dead_type:
            created = a.get("created_at", "")
            dead_zones.append({
                "anchor_id": aid[:20],
                "content": content[:60],
                "confidence": conf,
                "has_seal": has_seal,
                "steel_gap": steel_gap,
                "connections": conn,
                "neighbors": len(neighbors),
                "dead_type": dead_type,
                "created": created[:19] if created else "",
            })

    # ── 全局指标 ───────────────────────────────────────────────
    sealed = [a for a in real_anchors if len(a.get("seal_ids", [])) > 0]
    steel_density = len(sealed) / max(len(real_anchors), 1)
    orphan_nodes = [a for i, a in enumerate(real_anchors)
                    if not a.get("seal_ids") and connections[i] == 0]

    return {
        "triggered": len(dead_zones) > 0,
        "total_anchors": N,
        "test_anchors_filtered": test_count,
        "real_anchors_analyzed": len(real_anchors),
        "dead_zones": dead_zones,
        "probe_questions": _generate_probe_questions(dead_zones),
        "steel_density_pct": round(steel_density * 100, 1),
        "orphan_anchors": len(orphan_nodes),
        "avg_connections": round(sum(connections.values()) / max(len(real_anchors), 1), 2),
        "similarity_threshold": 0.35,
        "summary": _make_summary_v2(dead_zones, steel_density, orphan_nodes),
    }


def write_probe_to_body_regulation(probe_result: dict):
    """将探针结果写入 body_regulation.json"""
    if not probe_result.get("triggered"):
        return

    br_path = WS / "memory" / "body_regulation.json"
    try:
        br = json.loads(br_path.read_text(encoding="utf-8"))
    except Exception:
        br = {"signals": []}

    existing_ids = {s.get("anchor_id") for s in br.get("signals", [])
                    if isinstance(s, dict) and s.get("type") == "self_probe"}

    for dz in probe_result.get("dead_zones", []):
        aid = dz["anchor_id"]
        if aid in existing_ids:
            continue
        # 找对应探针问题
        q = next((x for x in probe_result.get("probe_questions", [])
                   if x["target"] == aid), {})
        br["signals"].append({
            "type": "self_probe",
            "subtype": dz["dead_type"],
            "anchor_id": aid,
            "content": dz["content"],
            "steel_gap": dz["steel_gap"],
            "confidence": dz["confidence"],
            "connections": dz["connections"],
            "question": q.get("question", ""),
        })

    probe_qs = probe_result.get("probe_questions", [])
    if probe_qs:
        existing_qs = {s.get("question") for s in br.get("signals", [])
                       if isinstance(s, dict) and s.get("type") == "self_probe_question"}
        for q in probe_qs:
            if q["question"] in existing_qs:
                continue
            br["signals"].append({
                "type": "self_probe_question",
                "subtype": q["type"],
                "question": q["question"],
                "anchor_id": q["target"],
                "steel_gap": q.get("steel_gap", 0),
            })

    # 同步 posture_zone
    gap_pct = probe_result.get("steel_density_pct", 100)
    if gap_pct < 20:
        br["posture_zone_probe"] = "steel_gap_critical"
    elif gap_pct < 35:
        br["posture_zone_probe"] = "steel_gap_warning"

    br_path.write_text(json.dumps(br, ensure_ascii=False, indent=2), encoding="utf-8")


# ── CLI ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TU-8 向内探针")
    parser.add_argument("--report", action="store_true", help="仅读取上次报告")
    args = parser.parse_args()

    report_path = WS / "memory" / "self_probe_report.json"

    if args.report:
        if report_path.exists():
            r = json.loads(report_path.read_text(encoding="utf-8"))
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print("无上次报告，重新扫描...")
        sys.exit(0)

    print("[向内探针] 开始扫描 DAG...")
    result = probe()

    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_probe_to_body_regulation(result)

    print(f"\n{'='*50}")
    print(f"分析锚点：{result['real_anchors_analyzed']}/{result['total_anchors']}（过滤测试数据 {result['test_anchors_filtered']} 个）")
    print(f"钢印密度：{result['steel_density_pct']}%")
    print(f"孤立锚点：{result['orphan_anchors']}")
    print(f"平均连接：{result['avg_connections']}")
    print(f"结构死区：{len(result['dead_zones'])}")
    print(f"\n{result['summary']}")

    if result.get("probe_questions"):
        print(f"\n{'─'*50}")
        print("🔥 探针问题：")
        for q in result["probe_questions"]:
            print(f"  [{q['type']}] {q['question']}")

    if result.get("dead_zones"):
        print(f"\n{'─'*50}")
        print("⚠️ 死区详情：")
        for dz in result["dead_zones"]:
            print(f"  [{dz['dead_type']}] conf={dz['confidence']} "
                  f"conn={dz['connections']} gap={dz['steel_gap']} "
                  f"'{dz['content'][:40]}'")
