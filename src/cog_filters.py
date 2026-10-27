# cog_filters.py - 认知过滤器:矩阵算法认知内核
# ==============================================================
# 目的:用数学矩阵算法做认知蒸馏,不是用算法的产品
#
# 内核(五种认知方式):
#   TimeFactor   = 信息密度的时间维度(e指数衰减)
#   Confidence   = 六维评分的置信度合成
#   InfoDensity  = Value × Confidence × TimeFactor(信息密度矩阵)
#   TopKFilter  = 硬截断(Top-K打分)
#   DAGCoherence = 因果连贯性(待接入)
# ==============================================================

import math
import time
from typing import List, Optional, Dict
from dataclasses import dataclass

# ── 默认配置 ──────────────────────────────────────────────────
LAMBDA_HOURS: float = 0.1     # 衰减率:每小时 -10%(e^(-0.1×1h))
DECAY_UNIT: str = "hours"     # 衰减单位:hours | days
DEFAULT_CONFIDENCE_WEIGHTS = {
    "freq": 0.15,
    "rel": 0.15,
    "div": 0.15,
    "cons": 0.20,    # 巩固度权重最高(最核心)
    "meaning": 0.20,  # 意义锚定次高
    "emotion": 0.15,
}


# ── TimeFactor:时间衰减算子 ────────────────────────────────
# 公式:TimeFactor = e^(-λ · Δt)
#
# λ=0.1/h → 半衰期 ≈ 6.9小时
# λ=0.01/h → 半衰期 ≈ 69小时(~3天)
# λ=0.005/h → 半衰期 ≈ 139小时(~5.8天)
#
# 与 recency() 的区别:
#   recency()  - 天为单位,用于晋升评分,半衰期14天
#   TimeFactor - 小时为单位,用于召回打分,半衰期可配置
# ==============================================================

def time_factor(
    last_recalled_at: Optional[float],
    created_at: float,
    lambda_hours: float = LAMBDA_HOURS,
    protection_level: int = 0,
    steelmarked: bool = False,
) -> float:
    """
    计算时间衰减因子(0.0 ~ 1.0)。

    语义:
        1.0 = 刚刚发生,无需衰减
        0.0 = 已过充分时间,理论上应被遗忘

    公式:TimeFactor = e^(-λ · Δt_hours)

    参数:
        last_recalled_at : 最近召回时间(秒),None=从未召回,用created_at
        created_at       : 创建时间(秒)
        lambda_hours     : 衰减率(每小时)
        protection_level : 0=普通, 1=重要, 2=核心(禁止衰减)
        steelmarked      : 是否钢印(极慢衰减)
    """
    # L1.5 核心保护区:禁止时间衰减
    if protection_level >= 2:
        return 1.0

    # 确定基准时间
    reference_ts = last_recalled_at if last_recalled_at is not None else created_at

    # 计算经过的小时数
    delta_hours = (time.time() - reference_ts) / 3600.0
    delta_hours = max(delta_hours, 0.0)

    # 钢印减缓衰减:λ 降低 10 倍
    effective_lambda = lambda_hours / 10.0 if steelmarked else lambda_hours

    return math.exp(-effective_lambda * delta_hours)


# ── Confidence:六维置信度合成 ──────────────────────────────
# 六维评分(全部≥0)天然匹配 NMF 的非负约束
# Confidence = Σ(wi · dimi) / Σwi  → 归一化到 [0, 1]
# ==============================================================

def entry_confidence(
    freq: float = 0.0,
    rel: float = 0.0,
    div: float = 0.0,
    cons: float = 0.0,
    meaning: float = 0.0,
    emotion: float = 0.0,
    weights: dict = None,
) -> float:
    """
    合成六维评分为单一置信度(0.0 ~ 1.0)。

    语义:
        高置信度 = 多维度均高 → 记忆条目稳固可靠
        低置信度 = 某维度拖后腿 → 不确定/碎片化

    NMF视角:六维非负 = NMF的W基向量,合成 = 加权叠加
    """
    w = weights or DEFAULT_CONFIDENCE_WEIGHTS
    raw = (
        w["freq"]    * min(freq,    1.0) +
        w["rel"]     * min(rel,     1.0) +
        w["div"]     * min(div,     1.0) +
        w["cons"]    * min(cons,    1.0) +
        w["meaning"] * min(meaning,  1.0) +
        w["emotion"] * min(emotion,  1.0)
    )
    total_weight = sum(w.values())  # 归一化分母
    return min(raw / total_weight, 1.0)


# ── InformationDensity:信息密度矩阵 ─────────────────────────
# 公式:InfoDensity = Value × Confidence × TimeFactor
#
# 数学本质:
#   - Value    : 检索相关性(输入Query × 记忆条目的相似度)
#   - Confidence: 六维评分合成(MemoryEntry内在可靠性)
#   - TimeFactor : 时间衰减(信息新鲜度)
#
# 等价于 SVD 的 Σ(重要性)对角矩阵在检索空间的投影
# ==============================================================

def information_density(
    query_similarity: float,   # Value: [0, 1]
    confidence: float,          # [0, 1]
    time_factor: float,         # [0, 1]
) -> float:
    """
    信息密度三因子乘积。

    语义:
        高密度 = 相关 + 可靠 + 新鲜 → 值得注入上下文
        低密度 = 不相关 OR 不可靠 OR 陈旧 → 丢弃

    与 recall() 内旧公式的差异:
        旧:similarity * 0.7 + recency * 0.3  (线性加权,有量纲不一致问题)
        新:Value × Confidence × TimeFactor     (无量纲乘积,符合信息论直觉)
    """
    return query_similarity * confidence * time_factor


# ── TopKFilter:硬截断 ───────────────────────────────────────
# 等价于 SVD 截断:保留 Top-K 个最大奇异值
# Score = InfoDensity → 取前K个 → 其余直接丢弃
# ==============================================================

def top_k_filter(
    entries: List[tuple],
    k: int = 10,
    score_key: str = "density",
) -> List[tuple]:
    """
    硬截断:只保留得分最高的 K 个条目。

    等价:SVD 截断 = 保留前 K 个最大 σi
    等价:Attention Mask 的硬版本(直接置零而非衰减)

    entries: [(entry, density_score), ...]
    """
    if len(entries) <= k:
        return entries
    # 按分数降序,取前K
    sorted_entries = sorted(entries, key=lambda x: x[1], reverse=True)
    return sorted_entries[:k]


# ── NMF冲突抑制 ───────────────────────────────────────────
# NMF约束:推理链只能叠加,不能相互否定
#
# 逻辑:
#   两个条目相互矛盾 → 高置信度保留,低置信度→0(禁止相互抵消)
#
# 矛盾检测策略:
#   1. 主题重叠(A和B谈论同一实体)
#   2. 极性冲突(A带否定信号,B不带)
#   3. 时间顺序:新 > 旧(同实体同极性时)
# ==============================================================

# 否定信号词
_NEGATION_PATTERNS = [
    r"不", r"没", r"无", r"非", r"不再", r"戒",
    r"已不", r"停止", r"取消", r"拒绝", r"否认",
    r"not", r"no", r"never", r"stopped", r"quit",
]

# 停用词(不参与主题重叠检测)
_STOP_WORDS = {
    # 中文单字（高频无意义填充词）
    "的", "是", "在", "了", "和", "与", "也", "都",
    "我", "你", "他", "她", "它", "这", "那", "一",
    "有", "一个", "什么", "怎么", "为", "很",
    "就", "到", "从", "把", "被", "让",
    "用", "户", "道", "只", "可", "要", "会", "能",
    "但", "而", "却", "虽", "虽", "好", "还", "再",
    "才", "又", "也", "更", "最", "还", "多", "少",
    # 中文双字填充（常见但无语义区分度）
    "用户", "我们", "他们", "你们", "自己", "这个", "那个",
    # 英文
    "the", "a", "an", "is", "are", "was", "were",
    "in", "on", "at", "to", "of", "and", "or",
}


def _extract_nuclear_terms(content: str) -> set:
    """
    提取核心理念词(去停用词后的关键词集合)。
    支持中英文混合:
      - 英文:按空格分词(自然语言空格分隔)
      - 中文:按字符提取有意义词(两个字以上视为词,否则用单字字符bigram)
    """
    import re
    terms = set()
    # 按空格+英文标点分词
    segments = re.split(r"[\s,.!?;:,。!?;:、]", content.lower())
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        # 判断语言:包含CJK字符=中文
        if re.search(r'[\u4e00-\u9fff]', seg):
            # 中文处理：停用词段直接丢弃
            if seg in _STOP_WORDS:
                continue
            # 两字以上视为词保留
            if len(seg) >= 2:
                terms.add(seg)
            # 单字（用于重叠检测，个别字符在停用词表也跳过）
            chars = [c for c in seg if not _is_cjk_punct(c)]
            for ch in chars:
                if ch not in _STOP_WORDS:
                    terms.add(ch)
        else:
            # 英文处理
            if len(seg) >= 2 and seg not in _STOP_WORDS:
                terms.add(seg)
    return terms


CJK_PUNCT = set(',。!?;:、,.!?;:()()【】《》')

def _is_cjk_punct(ch: str) -> bool:
    return ch in CJK_PUNCT


def _has_negation(content: str) -> bool:
    """检测内容是否带否定信号"""
    import re
    for pat in _NEGATION_PATTERNS:
        if re.search(pat, content):
            return True
    return False


def _nuclear_overlap(e1_content: str, e2_content: str) -> bool:
    """两个条目是否在核心理念层面重叠(存在共同主题)"""
    t1 = _extract_nuclear_terms(e1_content)
    t2 = _extract_nuclear_terms(e2_content)
    if not t1 or not t2:
        return False
    overlap = len(t1 & t2)
    union = len(t1 | t2)
    return (overlap / union) >= 0.2 if union > 0 else False


def _detect_conflict(entry1, entry2) -> bool:
    """检测两个条目是否相互矛盾(NMF约束下的禁止共存对)"""
    c1 = entry1.content
    c2 = entry2.content
    if not _nuclear_overlap(c1, c2):
        return False
    neg1 = _has_negation(c1)
    neg2 = _has_negation(c2)
    return neg1 != neg2  # 一个否定一个不否定 → 矛盾


def nmf_conflict_suppress(results: list) -> list:
    """
    NMF约束过滤:对相互矛盾的条目对,抑制低置信度者。

    NMF视角:
      SVD 允许线性组合 → 子结论可以相互抵消
      NMF 只允许加法组合 → 子结论只能叠加,不能否定

    规则:
      1. 矛盾检测(主题重叠 + 极性冲突)
      2. 高置信度赢,低置信度→0(不删除,只抑制)
      3. 置信度相等:时间新的赢
    """
    if len(results) <= 1:
        return results

    suppress: set = set()

    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            r1, r2 = results[i], results[j]
            if r1.entry.id in suppress or r2.entry.id in suppress:
                continue
            if not _detect_conflict(r1.entry, r2.entry):
                continue
            # 矛盾!高置信度赢
            if r1.score > r2.score:
                suppress.add(r2.entry.id)
            elif r2.score > r1.score:
                suppress.add(r1.entry.id)
            else:
                # 置信度相等:时间新的赢
                if r1.entry.created_at >= r2.entry.created_at:
                    suppress.add(r2.entry.id)
                else:
                    suppress.add(r1.entry.id)

    # 应用抑制(score→0,不删除,保持 MMR 多样性通道)
    for r in results:
        if r.entry.id in suppress:
            r.score = 0.0

    return results


# ── DAGCoherence:因果连贯性(预留) ─────────────────────────
# TODO: 等时间锚点→DAG骨架串联后接入
# 当前:恒返回 1.0(不施加额外惩罚)
# ==============================================================

# ── DAG 时间因果骨架 ───────────────────────────────────────────
# ================================================================
# DAG = Directed Acyclic Graph（时间有序有向无环图）
#
# 设计理念：
#   时间是单向的：事件A发生在事件B之前 → A→B 有向边
#   召回列表中若出现「B在A前面但B比A早发生」→ 因果断裂 → 降权
#
# 公式：
#   violation_ratio = (违反时间的<j对数) / 总<j对数
#   DAGCoherence = 1 - violation_ratio
#
#   例：[B, A]，B比A早发生 → 1对违反 → ratio=1/1=1 → coherence=0
#   例：[A, B]，B比A晚发生 → 0对违反 → ratio=0 → coherence=1
#
# 拓扑依据：anchors.json / memory/*.md 的 created_at 时间戳
# ================================================================

_DAG_CACHE: Optional[Dict[str, float]] = None
_DAG_CACHE_TS: float = 0.0
_DAG_CACHE_TTL: float = 300.0  # 5分钟缓存


def _load_entry_times() -> Dict[str, float]:
    """
    从 anchors.json 和 memory/*.md 加载所有记忆的时间戳。
    构建 entry_id → timestamp(float) 的字典。
    """
    import os, json, re
    from pathlib import Path

    workspace = Path(os.environ.get("QCLAW_WORKSPACE",
        r"C:\Users\qq366410837\.qclaw\workspace"))
    entry_times: Dict[str, float] = {}

    # 1. anchors.json
    anchor_file = workspace / "memory" / "anchors.json"
    if anchor_file.exists():
        try:
            data = json.loads(anchor_file.read_text(encoding="utf-8"))
            for anchor in data.get("anchors", []):
                aid = anchor.get("anchor_id", "")
                ts_str = anchor.get("created_at", "")
                if aid and ts_str:
                    try:
                        dt = __import__("datetime").datetime.fromisoformat(
                            ts_str.replace("Z", "+00:00").split("+")[0])
                        entry_times[aid] = dt.timestamp()
                    except Exception:
                        pass
        except Exception:
            pass

    # 2. memory/*.md 时间戳（从文件名和文件内容提取）
    mem_dir = workspace / "memory"
    for f in mem_dir.glob("????-??-??_*.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})_.*", f.stem)
        if m:
            date_str = m.group(1)
            # 默认时间：当天12:00
            dt = __import__("datetime").datetime.strptime(date_str, "%Y-%m-%d")
            entry_times[f.stem] = dt.timestamp()

    return entry_times


def _build_time_dag() -> Dict[str, float]:
    """构建并缓存 entry_id → timestamp(float) DAG底座"""
    global _DAG_CACHE, _DAG_CACHE_TS
    now = __import__("time").time()

    if _DAG_CACHE is not None and (now - _DAG_CACHE_TS) < _DAG_CACHE_TTL:
        return _DAG_CACHE

    _DAG_CACHE = _load_entry_times()
    _DAG_CACHE_TS = now
    return _DAG_CACHE


def dag_coherence_score(
    entry_id: str,
    recalled_order: List[str],
) -> float:
    """
    基于 DAG 时间因果链的连贯性打分（v2 真实实现）。

    参数：
        entry_id: 被评估的条目 ID
        recalled_order: 召回列表中所有条目的顺序（topK之前的原始顺序）

    语义：
        1.0 = 在因果链上，完全连贯
        <1.0 = 存在因果断裂（被降权）
        0.0 = 严重违反时间顺序

    公式：
        violation_ratio = (rank_i之后但timestamp_i之前<j的条目数) / C(n-i, 2)
        DAGCoherence = 1 - violation_ratio
    """
    if not recalled_order or entry_id not in recalled_order:
        return 1.0  # 不在召回列表，跳过

    dag_times = _build_time_dag()
    if not dag_times:
        return 1.0  # 无DAG数据，保守放行

    # 获取当前条目时间
    t_entry = dag_times.get(entry_id)
    if t_entry is None:
        return 1.0  # 无时间戳，保守放行

    # 找entry在召回列表的位置
    i = recalled_order.index(entry_id)

    # 统计违反：j>i 但 t_j < t_i
    total_pairs = 0
    violations = 0

    for j in range(i + 1, len(recalled_order)):
        other_id = recalled_order[j]
        t_other = dag_times.get(other_id)
        if t_other is None:
            continue
        total_pairs += 1
        if t_other < t_entry:
            violations += 1

    if total_pairs == 0:
        return 1.0  # 无可比较对象，保守放行

    ratio = violations / total_pairs
    return max(0.0, 1.0 - ratio)


def batch_dag_scores(recalled_order: List[str]) -> Dict[str, float]:
    """
    批量计算 DAG 连贯性分数（一次构建DAG，多次查询）。
    供 filter_and_rank 在批量召回时使用。

    返回：{entry_id: coherence_score, ...}
    """
    dag_times = _build_time_dag()
    if not dag_times:
        return {eid: 1.0 for eid in recalled_order}

    # 预排序：按时间顺序
    with_time = []
    for eid in recalled_order:
        t = dag_times.get(eid, float("inf"))
        with_time.append((eid, t))
    with_time.sort(key=lambda x: x[1])
    time_sorted = [eid for eid, _ in with_time]

    # 对每个条目计算违反比
    scores: Dict[str, float] = {}
    for eid in recalled_order:
        if eid not in dag_times:
            scores[eid] = 1.0
            continue

        t_entry = dag_times[eid]
        i_in_recall = recalled_order.index(eid)
        i_in_time = time_sorted.index(eid)

        # 实际违反：时间顺序在eid之前的条目，在召回中排在eid之后
        actual_later = [tid for tid in time_sorted if tid != eid and dag_times[tid] < t_entry]
        violations = sum(1 for tid in actual_later if recalled_order.index(tid) > i_in_recall)
        total = len(actual_later)

        if total == 0:
            scores[eid] = 1.0
        else:
            scores[eid] = max(0.0, 1.0 - violations / total)

    return scores


# ── 综合召回过滤器 ─────────────────────────────────────────
# 整合以上所有算子,一次调用完成召回打分
# =============================================================

@dataclass
class RecallScore:
    """召回打分结果"""
    entry_id: str
    density: float           # InformationDensity
    confidence: float         # 六维置信度
    time_factor: float       # 时间衰减
    query_similarity: float  # 原始相似度
    dag_coherence: float     # 因果连贯性(预留)
    final_score: float       # density × dag_coherence

    @property
    def is_high_density(self) -> bool:
        """信息密度阈值:>0.1 视为高密度(可注入上下文)"""
        return self.final_score > 0.1


def score_memory_entry(
    entry,               # MemoryEntry 对象
    query_similarity: float,
    lambda_hours: float = LAMBDA_HOURS,
    dag_enabled: bool = False,
    recalled_order: List[str] = None,  # 召回顺序，用于DAG连贯性计算
) -> RecallScore:
    """
    对单个记忆条目计算综合召回分数（v2含真实DAG连贯性）。

    等价于 SVD 的 Σ 谱分析在单条记忆上的投影。
    DAG连贯性验证：
        recalled_order 非空时，检查 entry 是否违反了时间因果顺序，
        若违反则 dag_coherence < 1.0，对应 final_score 降低。
    """
    # 1. TimeFactor
    tf = time_factor(
        last_recalled_at=getattr(entry, "last_recalled_at", None),
        created_at=entry.created_at,
        lambda_hours=lambda_hours,
        protection_level=getattr(entry, "protection_level", 0),
        steelmarked=getattr(entry, "steelmarked", False),
    )

    # 2. Confidence(NMF 合成)
    conf = entry_confidence(
        freq=getattr(entry, "freq", 0.0),
        rel=getattr(entry, "rel", 0.0),
        div=getattr(entry, "div", 0.0),
        cons=getattr(entry, "cons", 0.0),
        meaning=getattr(entry, "meaning", 0.0),
        emotion=getattr(entry, "emotion", 0.0),
    )

    # 3. InformationDensity
    density = information_density(query_similarity, conf, tf)

    # 4. DAG Coherence（v2：真实实现）
    dag_coh = 1.0
    if dag_enabled and recalled_order:
        dag_coh = dag_coherence_score(entry.id, recalled_order)

    # 5. Final Score
    final = density * dag_coh

    return RecallScore(
        entry_id=entry.id,
        density=density,
        confidence=conf,
        time_factor=tf,
        query_similarity=query_similarity,
        dag_coherence=dag_coh,
        final_score=final,
    )
