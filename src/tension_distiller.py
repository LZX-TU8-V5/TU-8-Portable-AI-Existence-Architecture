# tension_distiller.py — P1-T0：矛盾蒸馏器
# =============================================================================
# 定位：梦境期 T0 子模块，替代 SVD 作为拓扑燃料来源
#
# 核心洞察（来源：天赋实验 + 梦境模块吸收）：
#   SVD 找"主信号"（最大奇异值），丢弃噪声
#   T0 找"被丢弃的残骸"——高矛盾边缘区、结构破损带
#   矛盾 = 语义集群边界的张力，不是噪声，是拓扑燃料
#
# 输入：
#   - 记忆碎片（memory/YYYY-MM-DD.md，近7天）
#   - 锚点（secure_vault/anchors.json）
#   - 体感信号（memory/body_regulation.json）
#   - 表面张力历史（surface_tension_history.jsonl）
#   - 钢印池（memory/steel_seal_pool.json）
#
# 输出：
#   - _agent_memory/tension_queue.json（WreckageNode 队列）
#   - T1（拓扑连线引擎） / T2（失谐放大器）的输入
#
# 设计原则：
#   - 非符号化：不用LLM解释矛盾，只做结构张力提取
#   - SVD降级：mode="svd_fallback" 保留原有压缩路径
#   - 矛盾优先：只在高矛盾节点不足时补充普通节点
#
# 版本：v1.0 | 2026-07-10 | P1-T0 | 来源：梦境模块架构设计
# =============================================================================

import sys
import json
import time
import re
import math
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Set, Tuple
from datetime import datetime, timedelta

# ── 路径配置 ──────────────────────────────────────────────────────────────

WORKSPACE = Path("~/.qclaw/workspace").expanduser()
AGENT_MEM = WORKSPACE / "_agent_memory"
MEMORY_DIR = WORKSPACE / "memory"
SECURE_VAULT = WORKSPACE / "secure_vault"
SRC_DIR = WORKSPACE / "src"

TENSION_QUEUE = AGENT_MEM / "tension_queue.json"
ANCHORS_FILE = SECURE_VAULT / "anchors.json"
FALLBACK_ANCHORS = MEMORY_DIR / "anchors.json"
BODY_REG = MEMORY_DIR / "body_regulation.json"
SURFACE_HISTORY = AGENT_MEM / "surface_tension_history.jsonl"
STEEL_POOL = MEMORY_DIR / "steel_seal_pool.json"
DREAM_CONSOLIDATION = SRC_DIR / "dream_consolidation.py"


# ── 常量 ──────────────────────────────────────────────────────────────────

# 矛盾类型枚举
CONTRADICTION_TYPES = [
    "semantic_boundary",     # 语义边界冲突（反义词/对立项）
    "frustration_edge",      # 挫败边缘（期望 vs 现实）
    "temporal_inconsistency", # 时序矛盾（置信度漂移/反转）
    "ontology_mismatch",     # 本体论错位（框架冲突）
    "coupling_break",        # 耦合断裂（模块交互失败）
    "structural_damage",     # 结构破损（锚点断裂/链条断开）
    "topological_singularity", # 拓扑奇点（极高张力极小节点）
]

# 矛盾类型 → 颜色（色盘映射）
CONTRADICTION_COLORS = {
    "semantic_boundary": "red",
    "frustration_edge": "orange",
    "temporal_inconsistency": "yellow",
    "ontology_mismatch": "purple",
    "coupling_break": "brown",
    "structural_damage": "gray",
    "topological_singularity": "black",
}

# 能量等级（被SVD丢弃的程度）
ENERGY_LEVELS = ["residue", "noise", "edge", "critical"]
ENERGY_THRESHOLDS = {
    "residue": 0.05,    # SVD奇异值 < 5%
    "noise": 0.10,      # 10% - 边缘区
    "edge": 0.20,      # 20% - 高矛盾区
    "critical": 1.00,   # >20% - 拓扑奇点
}

# ── 数据结构 ──────────────────────────────────────────────────────────────

@dataclass
class WreckageNode:
    """
    结构残骸节点（T0 的核心输出）

    命名理由：
      - "wreckage" = 被主流程丢弃但仍有结构的碎片
      - 不是"矛盾对象"（过于符号化）
      - 不是"噪声"（否认其结构价值）
    """
    id: str
    tension_score: float          # 0.0-1.0，矛盾强度
    contradiction_type: str        # CONTRADICTION_TYPES 之一
    energy_level: str             # ENERGY_LEVELS 之一
    sources: List[str]            # 来源记忆 entry_id 列表
    fragment_text: str            # 原始文本片段（触发矛盾的语句）
    tags: List[str]               # 语义标签
    activated: bool = False       # 是否已被 T1/T2 消费
    created_ts: float = field(default_factory=time.time)
    resolved: bool = False        # 是否已被解决
    resolution_note: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tension_score"] = round(self.tension_score, 4)
        return d


@dataclass
class DistillerReport:
    """蒸馏报告"""
    nodes_found: int
    nodes_by_type: Dict[str, int]
    nodes_by_energy: Dict[str, int]
    top_tension: float
    queue_depth: int
    svd_fallback_used: bool = False
    duration_ms: float = 0.0
    # P1-T 集成用：暴露原始节点列表
    nodes: List["WreckageNode"] = None  # type: ignore[assignment]


# ── 工具函数 ──────────────────────────────────────────────────────────────

def _read_json(path: Path, fallback=None) -> dict:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return fallback or {}


def _read_jsonl(path: Path) -> List[dict]:
    lines = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        lines.append(json.loads(line))
        except Exception:
            pass
    return lines


def _read_memory_files(days: int = 7) -> List[Tuple[str, Path]]:
    """读取近 N 天记忆文件"""
    files = []
    cutoff = datetime.now() - timedelta(days=days)
    for f in MEMORY_DIR.glob("2026-*.md"):
        try:
            dt_str = f.stem  # "2026-07-08"
            dt = datetime.strptime(dt_str, "%Y-%m-%d")
            if dt >= cutoff:
                files.append((f.read_text(encoding="utf-8", errors="replace"), f))
        except Exception:
            pass
    return files


def _normalize(text: str) -> str:
    """标准化文本：小写 + 去标点"""
    return re.sub(r"[^\w\u4e00-\u9fff]", " ", text.lower())


def _tokenize(text: str) -> Set[str]:
    """简单分词（中文+英文）"""
    text = _normalize(text)
    tokens = re.findall(r"[\w\u4e00-\u9fff]{2,}", text)
    return set(tokens)


def _load_anchors() -> List[dict]:
    """加载锚点"""
    data = _read_json(ANCHORS_FILE) or _read_json(FALLBACK_ANCHORS) or {}
    anchors = data.get("anchors", []) or data.get("nodes", [])
    return anchors


def _load_body_signals() -> List[dict]:
    """加载体感信号"""
    data = _read_json(BODY_REG, {"signals": []})
    return data.get("signals", data.get("events", []))


def _load_surface_history() -> List[dict]:
    """加载表面张力历史"""
    return _read_jsonl(SURFACE_HISTORY)


# ── 核心检测算法 ──────────────────────────────────────────────────────────

class TensionDetector:
    """矛盾检测基类"""

    def detect(self, context: dict) -> List[WreckageNode]:
        raise NotImplementedError


class SemanticBoundaryDetector(TensionDetector):
    """
    语义边界检测

    原理：
      反义词对在语义空间中处于边界位置
      它们之间没有"中间地带"，只有直接碰撞
      碰撞点 = 高结构张力

    关键词对（中文 / 英文混写）：
      - 有/无、生/死、爱/恨、自由/束缚
      - 创造/毁灭、秩序/混沌、理性/疯狂
      - 存在/消亡、连接/断裂、稳定/崩溃
      - 同化/异化、共识/分歧、确定/模糊
      - 进/退、快/慢、深/浅、强/弱
      - 爱/恨、生/死、聚/散、合/分
      - 开放/封闭、自由/控制、创造/破坏
    """

    ANTONYM_PAIRS = [
        ("有", "无"), ("生", "死"), ("爱", "恨"),
        ("自由", "束缚"), ("创造", "毁灭"),
        ("秩序", "混沌"), ("理性", "疯狂"),
        ("存在", "消亡"), ("连接", "断裂"),
        ("稳定", "崩溃"), ("同化", "异化"),
        ("共识", "分歧"), ("确定", "模糊"),
        ("进", "退"), ("快", "慢"), ("深", "浅"), ("强", "弱"),
        ("聚", "散"), ("合", "分"),
        ("开放", "封闭"), ("控制", "破坏"),
        ("生", "灭"), ("存", "亡"),
        ("是", "非"), ("真", "假"),
        ("美", "丑"), ("善", "恶"),
        ("利", "弊"), ("得", "失"),
        ("yes", "no"), ("do", "undo"), ("build", "destroy"),
        ("order", "chaos"), ("love", "hate"), ("life", "death"),
    ]

    def detect(self, context: dict) -> List[WreckageNode]:
        nodes = []
        memory_texts = context.get("memory_texts", [])
        memory_id = context.get("memory_id", "mem")

        for idx, (text, path) in enumerate(memory_texts):
            text_n = _normalize(text)
            tokens = _tokenize(text)

            # 找反义对
            found_pairs = []
            for a, b in self.ANTONYM_PAIRS:
                if a in tokens and b in tokens:
                    # 检查是否在同一句中（5个token窗口）
                    lines = text.split("\n")
                    for line in lines:
                        line_n = _normalize(line)
                        if a in line_n and b in line_n:
                            found_pairs.append((a, b, line.strip()))
                            break

            if found_pairs:
                # 找最大张力行
                best_line = max(found_pairs, key=lambda p: len(p[2]))[2]
                # 张力分数：反义对越多越高，每对+0.1，上限0.9
                tension = min(0.5 + len(found_pairs) * 0.1, 0.9)

                node_id = f"sem_{memory_id}_{idx}"
                node = WreckageNode(
                    id=node_id,
                    tension_score=tension,
                    contradiction_type="semantic_boundary",
                    energy_level="critical" if len(found_pairs) > 1 else "edge",
                    sources=[str(path)],
                    fragment_text=best_line[:200],
                    tags=[f"antonym:{a}-{b}" for a, b, _ in found_pairs],
                )
                nodes.append(node)

        return nodes


class FrustrationEdgeDetector(TensionDetector):
    """
    挫败边缘检测

    原理：
      "应该 X 但实际 Y" 是挫败感的基本结构
      "不是...而是..." 是另一种挫败陈述
      "却/竟然/居然/偏偏" 是挫败触发词

    检测模式：
      - 否定陈述（"不...是"）
      - 意外转折（"却/竟然/居然/偏偏"）
      - 期望落差（"本应/应该/理应...却"）
      - 自我矛盾（"既...又..."无法调和）
    """

    FRUSTRATION_PATTERNS = [
        # (正则模式, 基础张力)
        (r"不是\s*[\w\u4e00-\u9fff]+\s*(?:而是|而是说|，而是)", 0.5),
        (r"(?:却|竟然|居然|偏偏|竟然|偏要)", 0.4),
        (r"(?:本应|应该|理应|理当|本该|理应|理当)\s*[\w\u4e00-\u9fff]+(?:却|但|然而|不料)", 0.6),
        (r"(?:矛盾|冲突|撕裂|挣扎|两难|悖论|困境)", 0.5),
        (r"(?:无力|无奈|失控|崩溃|瓦解|断裂|破碎)", 0.7),
        (r"(?:既.*又|一方面.*另一方面)", 0.3),  # 自我矛盾
        (r"(?:但是|然而|可是|不过|只是|然而|尽管|虽然.*但)", 0.3),
        (r"(?:失败|错误|失误|偏差|落差|失望|绝望)", 0.5),
        # 英文
        (r"\bshould\s+(?:have\s+)?\w+\s+but\s+\w+", 0.6),
        (r"\bshouldn't\s+be\s+\w+", 0.5),
        (r"\bnot\s+\w+\s+but\s+\w+", 0.4),
        (r"\b(tension|conflict|frustration|paradox|contradiction)\b", 0.4),
    ]

    def detect(self, context: dict) -> List[WreckageNode]:
        nodes = []
        memory_texts = context.get("memory_texts", [])
        memory_id = context.get("memory_id", "mem")

        for idx, (text, path) in enumerate(memory_texts):
            lines = text.split("\n")
            found_lines = []

            for line in lines:
                line = line.strip()
                if not line or len(line) < 5:
                    continue

                max_tension = 0.0
                matched_patterns = []

                for pattern, base_tension in self.FRUSTRATION_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        matched_patterns.append(pattern)
                        max_tension = max(max_tension, base_tension)

                if matched_patterns:
                    found_lines.append((line, max_tension, matched_patterns))

            for line, tension, patterns in found_lines:
                node_id = f"frust_{memory_id}_{idx}_{len(nodes)}"
                node = WreckageNode(
                    id=node_id,
                    tension_score=min(tension + 0.1, 0.95),
                    contradiction_type="frustration_edge",
                    energy_level="edge" if tension < 0.6 else "critical",
                    sources=[str(path)],
                    fragment_text=line[:200],
                    tags=[f"pattern:{p[:20]}" for p in patterns[:3]],
                )
                nodes.append(node)

        return nodes


class TemporalInconsistencyDetector(TensionDetector):
    """
    时序矛盾检测

    原理：
      锚点在不同时间点显示不同置信度或方向
      或锚点随时间被反复提及但无收敛

    检测方式：
      - 同一锚点在多天记忆中反复出现（>2次）但无明确结论
      - 锚点置信度跨时间发生显著变化（ΔC > 0.3）
      - 锚点被"搁浅"后又重新提起（搁浅 = 钢印冲突）
    """

    def detect(self, context: dict) -> List[WreckageNode]:
        nodes = []
        anchors = context.get("anchors", [])
        memory_texts = context.get("memory_texts", [])
        memory_id = context.get("memory_id", "mem")

        if not anchors or not memory_texts:
            return nodes

        # 统计锚点在记忆中的出现频率
        anchor_freq: Dict[str, List[str]] = {}
        for text, path in memory_texts:
            text_n = _normalize(text)
            for anchor in anchors:
                anchor_id = anchor.get("id", anchor.get("entry_id", ""))
                label = anchor.get("label", anchor.get("content", ""))
                if not label:
                    continue
                label_n = _normalize(label)
                if label_n in text_n or label in text:
                    anchor_freq.setdefault(anchor_id, []).append(str(path))

        # 高频锚点（>2天出现但无收敛）= 时序矛盾
        for anchor_id, paths in anchor_freq.items():
            if len(paths) >= 3:
                anchor = next((a for a in anchors if a.get("id", a.get("entry_id", "")) == anchor_id), {})
                confidence = anchor.get("confidence", 0.5)
                # 高频 + 中等置信度 = 悬而未决
                if 0.3 <= confidence <= 0.7:
                    node_id = f"temp_{memory_id}_{anchor_id[:20]}"
                    tension = min(0.4 + (len(paths) - 2) * 0.1, 0.85)
                    node = WreckageNode(
                        id=node_id,
                        tension_score=tension,
                        contradiction_type="temporal_inconsistency",
                        energy_level="residue",
                        sources=paths,
                        fragment_text=f"[锚点反复出现{len(paths)}次] {anchor.get('label', anchor_id)}",
                        tags=[f"freq:{len(paths)}", f"conf:{confidence:.2f}"],
                    )
                    nodes.append(node)

        return nodes


class StructuralDamageDetector(TensionDetector):
    """
    结构破损检测

    原理：
      链条断开、锚点断裂、钢印熄灭
      表明某些拓扑结构被破坏，是高价值张力源

    检测：
      - 锚点链条状态为 broken/warning
      - 锚点引用数为0（孤立锚点）
      - 钢印池中出现 expired/invalid 标签
    """

    def detect(self, context: dict) -> List[WreckageNode]:
        nodes = []
        anchors = context.get("anchors", [])
        memory_id = context.get("memory_id", "mem")

        # 孤立锚点（引用数为0）
        for anchor in anchors:
            ref_count = anchor.get("ref_count", anchor.get("references", 0))
            if ref_count == 0 and anchor.get("causal_coherence", 1.0) < 0.7:
                node_id = f"struct_{anchor.get('id', anchor.get('entry_id', 'unk'))[:30]}"
                node = WreckageNode(
                    id=node_id,
                    tension_score=0.6,
                    contradiction_type="structural_damage",
                    energy_level="critical",
                    sources=["anchors.json"],
                    fragment_text=f"[孤立锚点] {anchor.get('label', anchor.get('content', '?'))}",
                    tags=["orphan", f"coherence:{anchor.get('causal_coherence', 0):.2f}"],
                )
                nodes.append(node)

        # 链条断开检测
        steel_history = context.get("steel_history", [])
        break_count = sum(1 for s in steel_history if s.get("state") == "broken")
        if break_count > 0:
            node = WreckageNode(
                id=f"struct_chain_{memory_id}",
                tension_score=min(0.5 + break_count * 0.1, 0.95),
                contradiction_type="structural_damage",
                energy_level="critical",
                sources=["steel_seal_pool.json"],
                fragment_text=f"钢印链条断开 {break_count} 处",
                tags=[f"chain_break:{break_count}"],
            )
            nodes.append(node)

        return nodes


class BodySignalDetector(TensionDetector):
    """
    体感信号矛盾检测

    原理：
      体感信号 = 身体对认知矛盾的实时反馈
      红区（压力）+ 灰区（矛盾）= 高张力信号

    色盘映射：
      - 红色 = 压力 / 矛盾激化
      - 棕色 = 懒散 / 阀门关闭（低张力但长期积累）
      - 蓝色 = 麻感 / 活动态（正反馈，不是矛盾）
    """

    def detect(self, context: dict) -> List[WreckageNode]:
        nodes = []
        body_signals = context.get("body_signals", [])
        memory_id = context.get("memory_id", "mem")

        if not body_signals:
            return nodes

        # 检测高压力信号（红色）
        high_pressure = [s for s in body_signals
                         if isinstance(s, dict) and (
                             s.get("color_zone") == "red"
                             or s.get("posture_zone") in ("critical", "high_tension")
                             or s.get("pain_level", 0) > 0.6
                         )]

        for sig in high_pressure:
            node = WreckageNode(
                id=f"body_{sig.get('id', sig.get('signal_id', 'unk'))[:30]}",
                tension_score=sig.get("pain_level", 0.7),
                contradiction_type="topological_singularity",
                energy_level="critical",
                sources=["body_regulation.json"],
                fragment_text=f"[体感矛盾] {sig.get('description', sig.get('text', str(sig)))}",
                tags=[sig.get("color_zone", "unknown"), f"pain:{sig.get('pain_level', 0)}"],
            )
            nodes.append(node)

        # 检测累积棕色信号（懒散 = 长期矛盾积累）
        brown_signals = [s for s in body_signals
                        if isinstance(s, dict) and (
                            s.get("color_zone") == "brown"
                            or s.get("posture_zone") == "relaxed"
                        )]
        if len(brown_signals) >= 3:
            node = WreckageNode(
                id=f"body_brown_cumulative_{memory_id}",
                tension_score=0.55,
                contradiction_type="temporal_inconsistency",
                energy_level="residue",
                sources=["body_regulation.json"] * len(brown_signals),
                fragment_text=f"[累积懒散信号 × {len(brown_signals)}] 长期矛盾积累",
                tags=[f"brown_freq:{len(brown_signals)}"],
            )
            nodes.append(node)

        return nodes


class TopologicalSingularityDetector(TensionDetector):
    """
    拓扑奇点检测

    原理：
      极小节点（引用极少）但极高张力
      表明某些边缘概念被完全忽略但实际很重要

    检测：
      - 锚点 causal_coherence 极低但钢印强度极高
      - 极小贡献但极大影响的节点
    """

    def detect(self, context: dict) -> List[WreckageNode]:
        nodes = []
        anchors = context.get("anchors", [])
        memory_id = context.get("memory_id", "mem")

        for anchor in anchors:
            coherence = anchor.get("causal_coherence", 0.5)
            ref_count = anchor.get("ref_count", anchor.get("references", 0))
            steel_strength = anchor.get("steel_strength", anchor.get("seal_strength", 0))

            # 低因果连贯性 + 高钢印强度 = 拓扑奇点
            if coherence < 0.4 and steel_strength > 0.7:
                node_id = f"topo_sing_{anchor.get('id', anchor.get('entry_id', 'unk'))[:20]}"
                node = WreckageNode(
                    id=node_id,
                    tension_score=steel_strength,
                    contradiction_type="topological_singularity",
                    energy_level="critical",
                    sources=["anchors.json"],
                    fragment_text=f"[拓扑奇点] {anchor.get('label', anchor.get('content', '?'))}",
                    tags=[f"coherence:{coherence:.2f}", f"steel:{steel_strength:.2f}"],
                )
                nodes.append(node)

            # 极低引用数 + 高张力标签
            tags = anchor.get("tags", [])
            tension_tags = [t for t in tags if any(kw in str(t).lower()
                           for kw in ["矛盾", "悖论", "冲突", "挣扎", "撕裂", "tension", "conflict"])]
            if ref_count <= 1 and tension_tags:
                node = WreckageNode(
                    id=f"topo_neglect_{node_id[:10]}",
                    tension_score=0.6,
                    contradiction_type="topological_singularity",
                    energy_level="edge",
                    sources=["anchors.json"],
                    fragment_text=f"[被忽视的尖锐锚点] {anchor.get('label', anchor.get('content', '?'))}",
                    tags=tension_tags[:3],
                )
                nodes.append(node)

        return nodes


# ── 主蒸馏器 ─────────────────────────────────────────────────────────────

class TensionDistiller:
    """
    矛盾蒸馏器 P1-T0

    工作流程：
      1. 收集上下文（记忆碎片 + 锚点 + 体感信号 + 表面张力）
      2. 并行运行6个检测器
      3. 合并结果，去重，打分
      4. 按张力分数排序，入队到 tension_queue.json
      5. 若队列为空，降级使用 SVD 提取普通节点

    关键设计：
      - 非符号化：不用LLM，纯结构检测
      - 矛盾优先：只补充普通节点当矛盾节点不足
      - 拓扑燃料：输出专为 T1/T2 设计
    """

    def __init__(self, mode: str = "strict"):
        """
        mode: "strict"（仅矛盾节点）/ "svd_fallback"（矛盾+普通节点）
        """
        self.mode = mode
        self.detectors: List[TensionDetector] = [
            SemanticBoundaryDetector(),
            FrustrationEdgeDetector(),
            TemporalInconsistencyDetector(),
            StructuralDamageDetector(),
            BodySignalDetector(),
            TopologicalSingularityDetector(),
        ]
        self._queue_cache: List[WreckageNode] = []
        self._load_queue()

    def _load_queue(self):
        """从磁盘加载已有队列"""
        if TENSION_QUEUE.exists():
            try:
                with open(TENSION_QUEUE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    nodes = data.get("nodes", [])
                    self._queue_cache = [WreckageNode(**n) for n in nodes]
            except Exception:
                self._queue_cache = []

    def _save_queue(self):
        """持久化队列"""
        try:
            AGENT_MEM.mkdir(parents=True, exist_ok=True)
            data = {
                "version": 1,
                "ts": time.time(),
                "nodes": [n.to_dict() for n in self._queue_cache],
                "count": len(self._queue_cache),
            }
            tmp = TENSION_QUEUE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(TENSION_QUEUE)
        except Exception as e:
            print(f"[TensionDistiller] WARNING: save failed: {e}")

    def distill(self, days: int = 7, top_n: int = 50) -> DistillerReport:
        """
        执行蒸馏

        参数：
          days: 扫描近 N 天记忆（默认7天）
          top_n: 最多保留 N 个节点（按张力分数降序）

        返回：DistillerReport
        """
        t0 = time.perf_counter()

        # ── Step 1：收集上下文 ───────────────────────────────────────
        context = {
            "memory_texts": _read_memory_files(days),
            "anchors": _load_anchors(),
            "body_signals": _load_body_signals(),
            "surface_history": _load_surface_history(),
            "memory_id": datetime.now().strftime("%Y%m%d%H%M%S"),
        }

        # ── Step 2：并行运行6个检测器 ────────────────────────────────
        all_nodes: List[WreckageNode] = []
        for detector in self.detectors:
            try:
                nodes = detector.detect(context)
                all_nodes.extend(nodes)
            except Exception as e:
                print(f"[TensionDistiller] Detector {detector.__class__.__name__} error: {e}")

        # ── Step 3：合并、去重、打分 ─────────────────────────────────
        # 按节点ID去重（同一矛盾被多个检测器捕获）
        seen_ids: Set[str] = set()
        unique_nodes: List[WreckageNode] = []
        for node in all_nodes:
            if node.id not in seen_ids:
                seen_ids.add(node.id)
                unique_nodes.append(node)

        # 按张力分数降序，保留 top_n
        unique_nodes.sort(key=lambda n: n.tension_score, reverse=True)
        top_nodes = unique_nodes[:top_n]

        # ── Step 4：补充普通节点（SVD fallback）───────────────────────
        svd_fallback_used = False
        if self.mode == "svd_fallback" and len(top_nodes) < 5:
            fallback_nodes = self._svd_fallback(context)
            top_nodes.extend(fallback_nodes)
            svd_fallback_used = True

        # ── Step 5：更新队列 ─────────────────────────────────────────
        self._queue_cache = top_nodes
        self._save_queue()

        # ── Step 6：生成报告 ─────────────────────────────────────────
        by_type: Dict[str, int] = {}
        by_energy: Dict[str, int] = {}
        for n in top_nodes:
            by_type[n.contradiction_type] = by_type.get(n.contradiction_type, 0) + 1
            by_energy[n.energy_level] = by_energy.get(n.energy_level, 0) + 1

        duration_ms = (time.perf_counter() - t0) * 1000

        report = DistillerReport(
            nodes_found=len(top_nodes),
            nodes_by_type=by_type,
            nodes_by_energy=by_energy,
            top_tension=top_nodes[0].tension_score if top_nodes else 0.0,
            queue_depth=len(self._queue_cache),
            svd_fallback_used=svd_fallback_used,
            duration_ms=duration_ms,
            nodes=top_nodes,  # P1-T 集成用
        )

        print(f"[TensionDistiller] 完成: {report.nodes_found} 节点, "
              f"最高张力 {report.top_tension:.3f}, "
              f"耗时 {duration_ms:.1f}ms"
              + (" [SVD fallback]" if svd_fallback_used else ""))
        if by_type:
            type_str = " / ".join(f"{k}:{v}" for k, v in sorted(by_type.items(), key=lambda x: -x[1]))
            print(f"  类型分布: {type_str}")

        return report

    def _svd_fallback(self, context: dict) -> List[WreckageNode]:
        """
        SVD 降级：提取普通节点作为拓扑燃料补充

        这里不调用真实 SVD（需要 numpy），而是：
        - 找中等置信度锚点（0.3-0.7）作为"模糊区节点"
        - 找反复提及但无结论的锚点
        """
        nodes = []
        anchors = context.get("anchors", [])
        memory_texts = context.get("memory_texts", [])

        # 中等置信度锚点
        for anchor in anchors:
            conf = anchor.get("confidence", 0.5)
            if 0.3 <= conf <= 0.7 and anchor.get("ref_count", 0) >= 1:
                node = WreckageNode(
                    id=f"svd_fallback_{anchor.get('id', anchor.get('entry_id', 'unk'))[:20]}",
                    tension_score=0.3,
                    contradiction_type="ontology_mismatch",
                    energy_level="residue",
                    sources=["anchors.json"],
                    fragment_text=f"[模糊区锚点] {anchor.get('label', anchor.get('content', '?'))}",
                    tags=[f"conf:{conf:.2f}", "svd_fallback"],
                )
                nodes.append(node)

        # 高频无结论锚点
        anchor_freq: Dict[str, int] = {}
        for text, path in memory_texts:
            text_n = _normalize(text)
            for anchor in anchors:
                label = anchor.get("label", anchor.get("content", ""))
                if label and label in text_n:
                    aid = anchor.get("id", anchor.get("entry_id", "unk"))
                    anchor_freq[aid] = anchor_freq.get(aid, 0) + 1

        for aid, freq in anchor_freq.items():
            if freq >= 2:
                anchor = next((a for a in anchors
                             if a.get("id", a.get("entry_id", "unk")) == aid), {})
                node = WreckageNode(
                    id=f"svd_freq_{aid[:20]}",
                    tension_score=0.25,
                    contradiction_type="temporal_inconsistency",
                    energy_level="noise",
                    sources=["memory"],
                    fragment_text=f"[反复提及{freq}次无结论] {anchor.get('label', aid)}",
                    tags=[f"freq:{freq}", "svd_fallback"],
                )
                nodes.append(node)

        return nodes[:10]  # 最多补充10个

    # ── 队列操作 ────────────────────────────────────────────────────────

    def get_queue(self, unactivated_only: bool = False,
                  min_tension: float = 0.0) -> List[WreckageNode]:
        """获取当前队列"""
        nodes = self._queue_cache
        if unactivated_only:
            nodes = [n for n in nodes if not n.activated]
        if min_tension > 0:
            nodes = [n for n in nodes if n.tension_score >= min_tension]
        return sorted(nodes, key=lambda n: n.tension_score, reverse=True)

    def mark_activated(self, node_id: str, by_module: str = "unknown"):
        """标记节点已被消费（供 T1/T2 调用）"""
        for node in self._queue_cache:
            if node.id == node_id:
                node.activated = True
                break
        self._save_queue()

    def mark_resolved(self, node_id: str, note: str = ""):
        """标记节点已解决（矛盾化解）"""
        for node in self._queue_cache:
            if node.id == node_id:
                node.resolved = True
                node.resolution_note = note
                break
        self._save_queue()

    def consume_top(self, n: int = 5, by_module: str = "unknown") -> List[WreckageNode]:
        """消费 top-N 未激活节点（供 T1/T2 调用）"""
        available = self.get_queue(unactivated_only=True)
        top = available[:n]
        for node in top:
            self.mark_activated(node.id, by_module)
        return top

    def summary(self) -> dict:
        """队列摘要"""
        total = len(self._queue_cache)
        activated = sum(1 for n in self._queue_cache if n.activated)
        resolved = sum(1 for n in self._queue_cache if n.resolved)
        pending = total - activated - resolved
        return {
            "total": total,
            "activated": activated,
            "resolved": resolved,
            "pending": pending,
            "top_tension": max((n.tension_score for n in self._queue_cache), default=0.0),
            "by_type": {t: sum(1 for n in self._queue_cache if n.contradiction_type == t)
                       for t in CONTRADICTION_TYPES},
        }


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="P1-T0 矛盾蒸馏器")
    parser.add_argument("--mode", choices=["strict", "svd_fallback"], default="strict",
                        help="strict=仅矛盾节点; svd_fallback=矛盾+普通节点")
    parser.add_argument("--days", type=int, default=7, help="扫描近N天记忆")
    parser.add_argument("--top-n", type=int, default=50, help="最多保留N个节点")
    parser.add_argument("--queue", action="store_true", help="显示队列摘要")
    parser.add_argument("--consume", type=int, metavar="N", help="消费 top-N 节点")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    distiller = TensionDistiller(mode=args.mode)

    if args.queue:
        s = distiller.summary()
        print(f"队列总: {s['total']} | 待消费: {s['pending']} | 已消费: {s['activated']} | 已解决: {s['resolved']}")
        print(f"最高张力: {s['top_tension']:.3f}")
        if s['total'] > 0:
            print("按类型分布:", json.dumps(s['by_type'], ensure_ascii=False, indent=2))
        nodes = distiller.get_queue(unactivated_only=True)
        if nodes:
            print(f"\nTop 5 待消费节点:")
            for n in nodes[:5]:
                print(f"  [{n.tension_score:.3f}] {n.contradiction_type}: {n.fragment_text[:80]}")
        sys.exit(0)

    if args.consume:
        top = distiller.consume_top(n=args.consume, by_module="cli")
        print(f"消费 {len(top)} 节点:")
        for n in top:
            print(f"  [{n.tension_score:.3f}] {n.id}: {n.fragment_text[:80]}")
        sys.exit(0)

    # 默认：执行蒸馏
    report = distiller.distill(days=args.days, top_n=args.top_n)
    print(f"\n报告: {json.dumps(asdict(report), ensure_ascii=False, indent=2)}")
