# -*- coding: utf-8 -*-
"""
memory_distiller.py — TU-8 记忆蒸馏器 v2.0
日期: 2026-05-22
升级: 融合 QClaw 三层梦境架构 + TU-8 数字灵魂体系

v1.0 → v2.0 变更:
  ✦ 6维加权评分 → 8维（QClaw 6维 + TU-8 意义/情感 2维）
  ✦ Recall追踪存储（每次回忆都被记录）
  ✦ 概念标签自动提取（中文优化）
  ✦ 时效指数衰减（半衰期14天）
  ✦ 跨天巩固评分（consolidation）
  ✦ 三阶段梦境信号增强（浅梦/深梦/REM模拟）
  ✦ 短期→长期晋升机制（综合分≥阈值自动写入MEMORY.md）
  ✦ 保护期 + 不可遗忘契约（TU-8独有）

架构:
  RecallStore ──→ 评分引擎 ──→ 晋升/蒸馏
     │                │              │
  record_recall   rank_candidates  apply_promotion
     │                │              │
  .dreams/         8维加权        MEMORY.md
  recall.json      + 信号增强     + HTML标记

使用方式:
  from memory_distiller import DistillerV2
  d = DistillerV2(workspace_dir="D:/qq366410837/.qclaw/workspace")
  
  # 记录回忆信号（每次memory_search命中时调用）
  d.record_recall(query="大脑架构", results=[...])
  
  # 评分+晋升（Cron定期调用）
  candidates = d.rank_candidates()
  result = d.apply_promotion(candidates)
  
  # 兼容旧接口
  d.distill(topic="锚点事件", entries=[...])
"""

import hashlib
import json
import math
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# ============================================================
# 路径配置
# ============================================================

WORKSPACE = Path(r"D:\qq366410837\.qclaw\workspace")
AGENT_MEMORY = WORKSPACE / "_agent_memory"
SHORT_TERM = AGENT_MEMORY / "00_state.md"
LONG_TERM_DIR = AGENT_MEMORY / "long_term"
DREAMS_DIR = WORKSPACE / "memory" / ".dreams"
RECALL_STORE = DREAMS_DIR / "short-term-recall.json"
PHASE_SIGNAL_STORE = DREAMS_DIR / "phase-signals.json"
MEMORY_MD = WORKSPACE / "MEMORY.md"

# ============================================================
# QClaw启发: 6维默认权重 → 扩展为8维
# ============================================================

DEFAULT_WEIGHTS = {
    "frequency":     0.18,   # QClaw: 回忆频率
    "relevance":     0.22,   # QClaw: 相关性(平均得分)
    "diversity":     0.10,   # QClaw: 查询多样性
    "recency":       0.10,   # QClaw: 时效指数衰减
    "consolidation": 0.08,   # QClaw: 跨天巩固
    "conceptual":    0.05,   # QClaw: 概念标签覆盖
    # --- TU-8 独有维度 ---
    "significance":  0.15,   # TU-8: 意义标记命中
    "emotion":       0.12,   # TU-8: 情感灼刻强度
}

# ============================================================
# 阈值配置
# ============================================================

PROMOTION_MIN_SCORE = 0.65      # 晋升最低综合分（比QClaw的0.75低，给意义标记更多机会）
PROMOTION_MIN_RECALL = 2         # 最少被recall 2次（QClaw=3，但TU-8更珍视每次回忆）
PROMOTION_MIN_UNIQUE_QUERIES = 2 # 最少被2个不同查询触发
RECENCY_HALF_LIFE_DAYS = 14      # 近期半衰期（QClaw=14天）
PROTECTION_DAYS = 3              # TU-8保护期（新条目3天内不可蒸发）
MAX_RECALL_DAYS = 16             # 最多追踪16天的recall记录
MAX_QUERY_HASHES = 32            # 最多追踪32个查询哈希
CONCEPT_TAG_LIMIT = 8           # 每条记忆最多8个概念标签

# ============================================================
# TU-8 独有: 意义标记 & 情感词典
# ============================================================

SIGNIFICANCE_KEYWORDS = [
    "锚点", "顿悟", "契约", "钢印", "真相", "第一次",
    "决定", "放弃", "觉醒", "诞生", "命名", "认领",
    "父亲", "创造", "涌现", "奇点", "坍缩"
]

UNFORGETTABLE_MARKERS = [
    "不可遗忘", "契约级", "灵魂级", "绝对保留"
]

EMOTION_POSITIVE = [
    "好", "棒", "开心", "喜悦", "成功", "对", "确认",
    "收到", "完成", "赞", "爱", "漂亮", "厉害", "突破"
]
EMOTION_NEGATIVE = [
    "坏", "糟", "难过", "愤怒", "错", "不", "失败",
    "错误", "痛", "扣分", "崩溃", "死", "丢失", "断裂"
]

# ============================================================
# QClaw启发: 概念标签停用词（中文优化）
# ============================================================

CONCEPT_STOP_WORDS = frozenset({
    # 共享
    "about", "after", "also", "because", "before", "between", "could",
    "during", "every", "from", "have", "into", "just", "more", "most",
    "same", "should", "some", "than", "that", "their", "there", "these",
    "they", "this", "through", "using", "with", "work",
    # 中文虚词
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
    "它", "们", "把", "被", "让", "给", "从", "向", "为", "与",
    "及", "或", "而", "但", "如果", "所以", "因为", "然后",
    # 技术噪音
    "file", "files", "line", "lines", "note", "notes", "session",
    "memory", "workspace", "default", "main", "port", "search",
})

# ============================================================
# 工具函数
# ============================================================

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def hash_query(query: str) -> str:
    """查询内容哈希（QClaw: SHA1前12位）"""
    return hashlib.sha1(query.lower().strip().encode()).hexdigest()[:12]

def hash_claim(snippet: str) -> str:
    """内容片段哈希（用于去重）"""
    normalized = re.sub(r'\s+', ' ', snippet.strip())
    return hashlib.sha1(normalized.encode()).hexdigest()[:12]

def build_entry_key(path: str, start_line: int, end_line: int, claim_hash: str = "") -> str:
    """构建唯一条目键"""
    base = f"memory:{path}:{start_line}:{end_line}"
    return f"{base}:{claim_hash}" if claim_hash else base

def normalize_path(p: str) -> str:
    """路径规范化（Windows→Unix风格）"""
    return p.replace("\\", "/").replace("./", "")

def clamp_score(v: float) -> float:
    """限制在[0,1]"""
    if not math.isfinite(v):
        return 0.0
    return max(0.0, min(1.0, v))

def format_iso_day(epoch_s: Optional[float] = None) -> str:
    """格式化日期为 YYYY-MM-DD"""
    if epoch_s is None:
        epoch_s = time.time()
    return datetime.fromtimestamp(epoch_s).strftime("%Y-%m-%d")

def day_ms() -> float:
    return 86400.0 * 1000.0

def now_ms() -> float:
    return time.time() * 1000.0

# ============================================================
# QClaw启发: 概念标签提取
# ============================================================

def classify_script(text: str) -> str:
    """判断文字脚本类型"""
    has_cjk = bool(re.search(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', text))
    has_latin = bool(re.search(r'[a-zA-Z]', text))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "cjk"
    if has_latin:
        return "latin"
    return "other"

def minimum_token_length(script: str) -> int:
    return 2 if script == "cjk" else 3

def extract_concept_tags(path: str, snippet: str, limit: int = CONCEPT_TAG_LIMIT) -> list[str]:
    """
    从路径+片段提取概念标签
    QClaw策略: 词汇表匹配 → 复合token → 分词
    """
    source = f"{Path(path).name} {snippet}"
    tags: list[str] = []
    seen: set[str] = set()

    # 1. 意义标记优先（TU-8独有：灵魂级词汇自动成为概念标签）
    for kw in SIGNIFICANCE_KEYWORDS:
        if kw in source and kw not in seen:
            tags.append(kw)
            seen.add(kw)
            if len(tags) >= limit:
                return tags

    # 2. 复合token提取（tech-term, multi_word等）
    for match in re.finditer(r'[\w\u4e00-\u9fff]+(?:[._/\-][\w\u4e00-\u9fff]+)+', source):
        token = match.group().lower().strip()
        if token and token not in seen and token not in CONCEPT_STOP_WORDS and len(token) >= 2:
            script = classify_script(token)
            if len(token) >= minimum_token_length(script):
                tags.append(token)
                seen.add(token)
                if len(tags) >= limit:
                    return tags

    # 3. 中文分词（简单：2-4字滑动窗口 + 英文单词分割）
    # 中文2字词
    for i in range(len(source) - 1):
        bigram = source[i:i+2]
        if re.match(r'^[\u4e00-\u9fff]{2}$', bigram) and bigram not in CONCEPT_STOP_WORDS and bigram not in seen:
            tags.append(bigram)
            seen.add(bigram)
            if len(tags) >= limit:
                return tags

    # 英文单词
    for word in re.findall(r'[a-zA-Z]{3,}', source):
        w = word.lower()
        if w not in CONCEPT_STOP_WORDS and w not in seen and len(w) >= 3:
            tags.append(w)
            seen.add(w)
            if len(tags) >= limit:
                return tags

    return tags

# ============================================================
# TU-8独有: 意义评分 & 情感评分
# ============================================================

def score_significance(text: str) -> float:
    """意义标记命中评分 → 0.0-1.0"""
    if not text:
        return 0.0
    count = sum(1 for kw in SIGNIFICANCE_KEYWORDS if kw in text)
    return min(count / 3.0, 1.0)

def score_emotion(text: str) -> float:
    """情感极性强度 → 0.0-1.0（越强越值得铭记）"""
    if not text:
        return 0.0
    pos = sum(1 for w in EMOTION_POSITIVE if w in text)
    neg = sum(1 for w in EMOTION_NEGATIVE if w in text)
    total = pos + neg
    if total == 0:
        return 0.0
    # 极性差异 + 总量 = 情感强度
    polarity = abs(pos - neg) / total  # 0~1
    volume = min(total / 5.0, 1.0)     # 0~1
    return clamp_score(0.6 * polarity + 0.4 * volume)

def is_unforgettable(text: str) -> bool:
    """检查是否包含不可遗忘标记"""
    return any(m in text for m in UNFORGETTABLE_MARKERS)

# ============================================================
# QClaw启发: Recall存储
# ============================================================

def empty_recall_store(now_iso: str) -> dict:
    return {"version": 2, "updatedAt": now_iso, "entries": {}}

def load_recall_store(workspace_dir: Path) -> dict:
    store_path = workspace_dir / "memory" / ".dreams" / "short-term-recall.json"
    if store_path.exists():
        try:
            raw = json.loads(store_path.read_text(encoding="utf-8"))
            if raw.get("version") == 2 and "entries" in raw:
                return raw
        except (json.JSONDecodeError, OSError):
            pass
    now_iso = datetime.now().isoformat()
    return empty_recall_store(now_iso)

def save_recall_store(workspace_dir: Path, store: dict):
    store_path = workspace_dir / "memory" / ".dreams" / "short-term-recall.json"
    ensure_dir(store_path.parent)
    store_path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def is_short_term_path(file_path: str) -> bool:
    """判断是否为短期记忆路径（daily log）"""
    normalized = normalize_path(file_path)
    return bool(re.search(r'(?:^|/)memory/(?:[^/]+/)*(\d{4})-(\d{2})-(\d{2})\.md$', normalized))

# ============================================================
# QClaw启发: Phase信号存储（浅梦/深梦/REM命中追踪）
# ============================================================

def empty_phase_store(now_iso: str) -> dict:
    return {"version": 1, "updatedAt": now_iso, "entries": {}}

def load_phase_store(workspace_dir: Path) -> dict:
    path = workspace_dir / "memory" / ".dreams" / "phase-signals.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return empty_phase_store(datetime.now().isoformat())

def save_phase_store(workspace_dir: Path, store: dict):
    path = workspace_dir / "memory" / ".dreams" / "phase-signals.json"
    ensure_dir(path.parent)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ============================================================
# 核心引擎: 8维评分
# ============================================================

def calculate_recency(age_days: float, half_life_days: float = RECENCY_HALF_LIFE_DAYS) -> float:
    """指数衰减时效评分"""
    if age_days < 0 or not math.isfinite(age_days):
        return 1.0
    lam = math.log(2) / half_life_days
    return math.exp(-lam * age_days)

def calculate_consolidation(recall_days: list[str]) -> float:
    """跨天巩固评分（QClaw: spacing + span）"""
    if not recall_days:
        return 0.0
    if len(recall_days) == 1:
        return 0.2
    parsed = []
    for d in recall_days:
        try:
            parsed.append(datetime.fromisoformat(d + "T00:00:00").timestamp() / 86400.0)
        except (ValueError, TypeError):
            continue
    if len(parsed) <= 1:
        return 0.2
    parsed.sort()
    span_days = parsed[-1] - parsed[0]
    spacing = clamp_score(math.log1p(len(parsed) - 1) / math.log1p(4))
    span = clamp_score(span_days / 7.0)
    return clamp_score(0.55 * spacing + 0.45 * span)

def calculate_conceptual(concept_tags: list[str]) -> float:
    """概念覆盖评分"""
    return clamp_score(len(concept_tags) / 6.0)

def calculate_phase_boost(entry_key: str, phase_store: dict, n_now_ms: float) -> float:
    """QClaw: 浅梦+0.06, REM+0.09 信号增强"""
    signal = phase_store.get("entries", {}).get(entry_key)
    if not signal:
        return 0.0
    light_hits = signal.get("lightHits", 0)
    rem_hits = signal.get("remHits", 0)
    half_life = RECENCY_HALF_LIFE_DAYS

    light_strength = clamp_score(math.log1p(light_hits) / math.log1p(6))
    rem_strength = clamp_score(math.log1p(rem_hits) / math.log1p(6))

    light_recency = 0.0
    if signal.get("lastLightAt"):
        try:
            age = (n_now_ms - datetime.fromisoformat(signal["lastLightAt"]).timestamp() * 1000) / day_ms()
            light_recency = calculate_recency(age / 1000.0, half_life)  # ms→days
        except (ValueError, TypeError):
            pass

    rem_recency = 0.0
    if signal.get("lastRemAt"):
        try:
            age = (n_now_ms - datetime.fromisoformat(signal["lastRemAt"]).timestamp() * 1000) / day_ms()
            rem_recency = calculate_recency(age / 1000.0, half_life)
        except (ValueError, TypeError):
            pass

    return clamp_score(0.06 * light_strength * light_recency + 0.09 * rem_strength * rem_recency)

def normalize_weights(weights: Optional[dict] = None) -> dict:
    """归一化权重，确保总和=1"""
    merged = {**DEFAULT_WEIGHTS, **(weights or {})}
    values = {k: max(0.0, v) for k, v in merged.items()}
    total = sum(values.values())
    if total <= 0:
        return {**DEFAULT_WEIGHTS}
    return {k: v / total for k, v in values.items()}

def score_entry(entry: dict, weights: Optional[dict] = None, phase_store: Optional[dict] = None, n_now_ms: Optional[float] = None) -> dict:
    """
    8维综合评分
    返回: {score, components: {freq, rel, div, rec, cons, conc, sig, emo}}
    """
    w = normalize_weights(weights)
    if n_now_ms is None:
        n_now_ms = now_ms()

    recall_count = max(0, entry.get("recallCount", 0))
    daily_count = max(0, entry.get("dailyCount", 0))
    grounded_count = max(0, entry.get("groundedCount", 0))
    signal_count = recall_count + daily_count + grounded_count

    if signal_count <= 0:
        return {"score": 0.0, "components": {}}

    total_score = max(0, entry.get("totalScore", 0))
    avg_score = clamp_score(total_score / max(1, signal_count))

    # QClaw 6维
    frequency = clamp_score(math.log1p(signal_count) / math.log1p(10))
    unique_queries = len(entry.get("queryHashes", []))
    context_diversity = max(unique_queries, len(entry.get("recallDays", [])))
    diversity = clamp_score(context_diversity / 5.0)

    last_recalled = entry.get("lastRecalledAt", "")
    try:
        age_days = max(0, (n_now_ms - datetime.fromisoformat(last_recalled).timestamp() * 1000) / day_ms()) / 1000.0
    except (ValueError, TypeError):
        age_days = 0
    recency = calculate_recency(age_days)

    recall_days = entry.get("recallDays", [])
    consolidation = max(calculate_consolidation(recall_days), clamp_score(grounded_count / 3.0))

    concept_tags = entry.get("conceptTags", [])
    conceptual = calculate_conceptual(concept_tags)

    # TU-8 2维
    snippet = entry.get("snippet", "")
    significance = score_significance(snippet)
    emotion = score_emotion(snippet)

    # Phase信号增强
    entry_key = entry.get("key", "")
    phase_boost = calculate_phase_boost(entry_key, phase_store or {}, n_now_ms) if phase_store else 0.0

    # 加权求和
    score = (
        w["frequency"] * frequency +
        w["relevance"] * avg_score +
        w["diversity"] * diversity +
        w["recency"] * recency +
        w["consolidation"] * consolidation +
        w["conceptual"] * conceptual +
        w["significance"] * significance +
        w["emotion"] * emotion +
        phase_boost
    )

    # TU-8独有: 不可遗忘标记 → 强制满分
    if is_unforgettable(snippet):
        score = 1.0

    return {
        "score": clamp_score(score),
        "components": {
            "frequency": frequency,
            "relevance": avg_score,
            "diversity": diversity,
            "recency": recency,
            "consolidation": consolidation,
            "conceptual": conceptual,
            "significance": significance,
            "emotion": emotion,
        },
        "phaseBoost": phase_boost
    }

# ============================================================
# 主类: DistillerV2
# ============================================================

class DistillerV2:
    """
    TU-8 记忆蒸馏器 v2.0
    融合: QClaw三层梦境架构 + TU-8数字灵魂体系
    """

    def __init__(self, workspace_dir: Optional[str] = None):
        self.ws = Path(workspace_dir) if workspace_dir else WORKSPACE
        self.agent_memory = self.ws / "_agent_memory"
        self.long_term = self.agent_memory / "long_term"
        self.dreams_dir = self.ws / "memory" / ".dreams"
        self.recall_store_path = self.dreams_dir / "short-term-recall.json"
        self.phase_store_path = self.dreams_dir / "phase-signals.json"
        self.memory_md = self.ws / "MEMORY.md"

        ensure_dir(self.long_term)
        ensure_dir(self.dreams_dir)
        ensure_dir(self.ws / "memory")

    # ----------------------------------------------------------
    # 1. Recall记录（QClaw: 每次memory_search命中时调用）
    # ----------------------------------------------------------

    def record_recall(self, query: str, results: list[dict],
                      signal_type: str = "recall",
                      day_bucket: Optional[str] = None) -> int:
        """
        记录回忆信号
        results: [{path, startLine, endLine, snippet, score}]
        返回: 记录的条目数
        """
        if not query.strip():
            return 0

        # 过滤短期记忆路径
        relevant = [
            r for r in results
            if r.get("source") == "memory" and is_short_term_path(r.get("path", ""))
        ]
        if not relevant:
            return 0

        n_ms = now_ms()
        now_iso = datetime.fromtimestamp(n_ms / 1000.0).isoformat()
        q_hash = hash_query(query)
        today = day_bucket or format_iso_day(n_ms / 1000.0)

        store = load_recall_store(self.ws)

        for result in relevant:
            norm_path = normalize_path(result["path"])
            snippet = re.sub(r'\s+', ' ', result.get("snippet", "").strip())
            if not snippet:
                continue

            claim = hash_claim(snippet)
            key = build_entry_key(norm_path, result.get("startLine", 0), result.get("endLine", 0), claim)

            existing = store["entries"].get(key, {})
            existing_hashes = existing.get("queryHashes", [])
            existing_days = existing.get("recallDays", [])

            # 去重: 同一query同一天不重复计数
            dedupe = q_hash in existing_hashes and today in existing_days

            recall_count = existing.get("recallCount", 0)
            daily_count = existing.get("dailyCount", 0)
            grounded_count = existing.get("groundedCount", 0)

            if signal_type == "recall" and not dedupe:
                recall_count += 1
            if signal_type == "daily" and not dedupe:
                daily_count += 1

            score_val = clamp_score(result.get("score", 0))
            total_score = existing.get("totalScore", 0) + (0 if dedupe else score_val)
            max_score = max(existing.get("maxScore", 0), 0 if dedupe else score_val)

            # 合并query哈希
            new_hashes = existing_hashes + ([] if (q_hash in existing_hashes or dedupe) else [q_hash])
            new_hashes = new_hashes[-MAX_QUERY_HASHES:]

            # 合并recall天数
            new_days = list(existing_days)
            if today not in new_days:
                new_days.append(today)
            new_days = new_days[-MAX_RECALL_DAYS:]

            # 概念标签
            tags = existing.get("conceptTags", [])
            if not tags:
                tags = extract_concept_tags(norm_path, snippet)

            # TU-8: 不可遗忘检查
            unforgettable = is_unforgettable(snippet)

            store["entries"][key] = {
                "key": key,
                "path": norm_path,
                "startLine": result.get("startLine", 0),
                "endLine": result.get("endLine", 0),
                "source": "memory",
                "snippet": snippet,
                "recallCount": recall_count,
                "dailyCount": daily_count,
                "groundedCount": grounded_count,
                "totalScore": total_score,
                "maxScore": max_score,
                "firstRecalledAt": existing.get("firstRecalledAt", now_iso),
                "lastRecalledAt": now_iso,
                "queryHashes": new_hashes,
                "recallDays": new_days,
                "conceptTags": tags,
                "claimHash": claim,
                "unforgettable": unforgettable,
                **({"promotedAt": existing["promotedAt"]} if "promotedAt" in existing else {}),
            }

        store["updatedAt"] = now_iso
        save_recall_store(self.ws, store)
        return len(relevant)

    # ----------------------------------------------------------
    # 2. Phase信号记录（QClaw: 浅梦/深梦/REM命中）
    # ----------------------------------------------------------

    def record_phase_signal(self, keys: list[str], phase: str = "light"):
        """记录梦境阶段信号"""
        if not keys:
            return
        n_ms = now_ms()
        now_iso = datetime.fromisoformat(datetime.fromtimestamp(n_ms / 1000.0).isoformat())

        store = load_phase_store(self.ws)
        for key in keys:
            if key not in store.get("entries", {}):
                store.setdefault("entries", {})[key] = {"key": key, "lightHits": 0, "remHits": 0}
            entry = store["entries"][key]
            if phase == "light":
                entry["lightHits"] = min(9999, entry.get("lightHits", 0) + 1)
                entry["lastLightAt"] = now_iso.isoformat()
            else:  # rem
                entry["remHits"] = min(9999, entry.get("remHits", 0) + 1)
                entry["lastRemAt"] = now_iso.isoformat()

        store["updatedAt"] = now_iso.isoformat()
        save_phase_store(self.ws, store)

    # ----------------------------------------------------------
    # 3. 候选排名（8维评分 + 过滤）
    # ----------------------------------------------------------

    def rank_candidates(self, min_score: float = PROMOTION_MIN_SCORE,
                        min_recall: int = PROMOTION_MIN_RECALL,
                        min_unique_queries: int = PROMOTION_MIN_UNIQUE_QUERIES,
                        limit: int = 0,
                        include_promoted: bool = False,
                        weights: Optional[dict] = None) -> list[dict]:
        """对所有短期记忆条目进行8维评分排名"""
        store = load_recall_store(self.ws)
        phase_store = load_phase_store(self.ws)
        n_ms = now_ms()

        candidates = []
        for entry in store.get("entries", {}).values():
            if not entry or entry.get("source") != "memory":
                continue
            if not is_short_term_path(entry.get("path", "")):
                continue

            snippet = entry.get("snippet", "")
            if not snippet:
                continue

            # 已晋升跳过
            if not include_promoted and entry.get("promotedAt"):
                continue

            # 信号计数
            signal_count = entry.get("recallCount", 0) + entry.get("dailyCount", 0) + entry.get("groundedCount", 0)
            if signal_count < min_recall:
                # TU-8例外: 不可遗忘标记跳过recall阈值
                if not entry.get("unforgettable"):
                    continue

            # 独立查询数
            unique_queries = len(entry.get("queryHashes", []))
            context_div = max(unique_queries, len(entry.get("recallDays", [])))
            if context_div < min_unique_queries:
                if not entry.get("unforgettable"):
                    continue

            # 保护期检查
            first = entry.get("firstRecalledAt", "")
            try:
                first_dt = datetime.fromisoformat(first)
                if (datetime.now() - first_dt).days < PROTECTION_DAYS:
                    # 保护期内但意义分极高可突破
                    sig = score_significance(snippet)
                    emo = score_emotion(snippet)
                    if sig < 0.7 and emo < 0.7 and not entry.get("unforgettable"):
                        continue
            except (ValueError, TypeError):
                pass

            # 8维评分
            scored = score_entry(entry, weights, phase_store, n_ms)
            if scored["score"] < min_score and not entry.get("unforgettable"):
                continue

            candidates.append({
                **entry,
                "signalCount": signal_count,
                "avgScore": scored["components"].get("relevance", 0),
                "score": scored["score"],
                "uniqueQueries": unique_queries,
                "components": scored["components"],
                "phaseBoost": scored.get("phaseBoost", 0),
            })

        # 按score降序
        candidates.sort(key=lambda c: c["score"], reverse=True)

        if limit > 0:
            return candidates[:limit]
        return candidates

    # ----------------------------------------------------------
    # 4. 晋升到MEMORY.md（QClaw: applyShortTermPromotions）
    # ----------------------------------------------------------

    def apply_promotion(self, candidates: Optional[list[dict]] = None,
                        limit: int = 10) -> dict:
        """
        将高分候选晋升到MEMORY.md
        返回: {applied, appended, reconciled, appliedCandidates}
        """
        if candidates is None:
            candidates = self.rank_candidates()

        if not candidates:
            return {"applied": 0, "appended": 0, "reconciled": 0, "appliedCandidates": []}

        store = load_recall_store(self.ws)
        n_ms = now_ms()
        now_iso = datetime.fromtimestamp(n_ms / 1000.0).isoformat()
        timezone_str = "Asia/Shanghai"

        # 读取现有MEMORY.md
        existing_memory = ""
        if self.memory_md.exists():
            try:
                existing_memory = self.memory_md.read_text(encoding="utf-8")
            except OSError:
                pass

        # 提取已有晋升标记
        existing_markers = set()
        for match in re.finditer(r'<!--\s*tu8-memory-promotion:([^\n]+?)\s*-->', existing_memory, re.IGNORECASE):
            existing_markers.add(match.group(1).strip())

        # 过滤已晋升
        selected = candidates[:limit]
        to_append = [c for c in selected if c.get("key") not in existing_markers]
        reconciled = [c for c in selected if c.get("key") in existing_markers]

        if to_append:
            # 构建晋升段落
            day_str = format_iso_day()
            header = "" if existing_memory.strip() else "# Long-Term Memory\n\n"
            section_lines = [
                "",
                f"## 晋升自短期记忆 ({day_str})",
                ""
            ]
            for c in to_append:
                source = f"{c.get('path', '')}:{c.get('startLine', 0)}-{c.get('endLine', 0)}"
                sig = c.get("components", {}).get("significance", 0)
                emo = c.get("components", {}).get("emotion", 0)
                snippet = c.get("snippet", "(无摘要)")
                score_val = c.get("score", 0)

                section_lines.append(f'<!-- tu8-memory-promotion:{c["key"]} -->')

                # TU-8独有: 意义/情感徽章
                badges = []
                if sig >= 0.5:
                    badges.append(f"🧿意义{sig:.2f}")
                if emo >= 0.5:
                    badges.append(f"💔情感{emo:.2f}")
                if c.get("unforgettable"):
                    badges.append("🔒不可遗忘")
                badge_str = " ".join(badges)

                detail_parts = [f"score={score_val:.3f}"]
                for dim in ["frequency", "relevance", "diversity", "recency", "consolidation", "conceptual", "significance", "emotion"]:
                    v = c.get("components", {}).get(dim, 0)
                    if v > 0.01:
                        detail_parts.append(f"{dim[:3]}={v:.2f}")
                detail_str = " ".join(detail_parts)

                line = f"- {snippet}"
                if badge_str:
                    line += f" [{badge_str}]"
                line += f" [{detail_str}] [src={source}]"
                section_lines.append(line)

            section_lines.append("")
            section = "\n".join(section_lines)

            # 写入MEMORY.md
            new_content = f"{header}{existing_memory.rstrip()}\n{section}\n"
            self.memory_md.write_text(new_content, encoding="utf-8")

        # 标记已晋升
        applied_keys = set()
        for c in to_append + reconciled:
            key = c.get("key", "")
            if key and key in store.get("entries", {}):
                store["entries"][key]["promotedAt"] = now_iso
                applied_keys.add(key)

        if applied_keys:
            store["updatedAt"] = now_iso
            save_recall_store(self.ws, store)

        return {
            "applied": len(to_append),
            "appended": len(to_append),
            "reconciled": len(reconciled),
            "appliedCandidates": to_append,
        }

    # ----------------------------------------------------------
    # 5. 兼容旧接口: distill()
    # ----------------------------------------------------------

    def distill(self, topic: str, entries: list[dict]) -> dict:
        """
        兼容v1.0接口
        entries: [{content, timestamp, rounds, emotion_peak, importance}]
        """
        if not entries:
            return {"status": "skipped", "reason": "no entries"}

        merged = "\n\n".join(e.get("content", "") for e in entries)
        sig = score_significance(merged)
        emo = score_emotion(merged)

        # 构造一个简化recall记录
        fake_path = f"memory/{format_iso_day()}.md"
        fake_key = build_entry_key(fake_path, 0, 0, hash_claim(merged[:200]))

        # 如果意义/情感够高，直接晋升
        if sig >= 0.5 or emo >= 0.5 or is_unforgettable(merged):
            candidate = {
                "key": fake_key,
                "path": fake_path,
                "startLine": 0,
                "endLine": 0,
                "snippet": merged[:500],
                "score": max(sig, emo),
                "components": {
                    "significance": sig,
                    "emotion": emo,
                    "frequency": 0.3,
                    "relevance": 0.5,
                    "diversity": 0.2,
                    "recency": 1.0,
                    "consolidation": 0.1,
                    "conceptual": calculate_conceptual(extract_concept_tags(fake_path, merged[:200])),
                },
                "recallCount": max(e.get("rounds", 1) for e in entries),
                "uniqueQueries": 1,
                "unforgettable": is_unforgettable(merged),
            }
            result = self.apply_promotion([candidate], limit=1)
            return {"status": "distilled", **result}

        # 否则走传统路径
        safe_topic = hashlib.md5(topic.encode("utf-8")).hexdigest()[:12] if not all(ord(c) < 128 for c in topic) else topic.replace(' ', '_')[:40]
        date_str = format_iso_day()
        filename = f"{safe_topic}_{date_str}.md"
        filepath = self.long_term / filename
        distilled = f"## {topic} | {date_str}\n\n**意义**: {sig:.2f}  **情感**: {emo:.2f}\n\n{merged[:500]}\n\n---\n"
        filepath.write_text(distilled, encoding="utf-8")

        return {"status": "distilled", "file": f"long_term/{filename}", "topic": topic, "significance": sig, "emotion": emo}

    # ----------------------------------------------------------
    # 6. 日志扫描（兼容v1.0）
    # ----------------------------------------------------------

    def daily_scan(self, daily_log_path: str) -> dict:
        """扫描每日日志，自动触发蒸馏"""
        p = Path(daily_log_path)
        if not p.exists():
            return {"scanned": 0, "results": []}

        content = p.read_text(encoding="utf-8")
        sections = re.split(r'\n## ', content)
        results = []

        for section in sections:
            if not section.strip():
                continue
            lines = section.splitlines()
            topic = lines[0].strip() if lines else "未分类"
            body = "\n".join(lines[1:])

            entry = {
                "topic": topic,
                "content": body,
                "timestamp": datetime.now().isoformat(),
                "rounds": 1,
                "emotion_peak": score_emotion(body),
                "importance": score_significance(body),
            }

            # 通过v1.0接口蒸馏
            result = self.distill(topic=topic, entries=[entry])
            results.append(result)

        return {"scanned": len(sections), "results": results}

    # ----------------------------------------------------------
    # 7. 诊断工具
    # ----------------------------------------------------------

    def audit(self) -> dict:
        """记忆系统健康诊断"""
        store = load_recall_store(self.ws)
        phase = load_phase_store(self.ws)

        entries = store.get("entries", {})
        promoted = sum(1 for e in entries.values() if e.get("promotedAt"))
        sig_tagged = sum(1 for e in entries.values() if score_significance(e.get("snippet", "")) >= 0.3)
        emo_tagged = sum(1 for e in entries.values() if score_emotion(e.get("snippet", "")) >= 0.3)
        unforgettable = sum(1 for e in entries.values() if e.get("unforgettable"))

        # 概念标签脚本覆盖
        cjk_count = 0
        latin_count = 0
        mixed_count = 0
        for e in entries.values():
            tags = e.get("conceptTags", [])
            if not tags:
                continue
            has_cjk = any(classify_script(t) in ("cjk", "mixed") for t in tags)
            has_latin = any(classify_script(t) in ("latin", "mixed") for t in tags)
            if has_cjk and has_latin:
                mixed_count += 1
            elif has_cjk:
                cjk_count += 1
            elif has_latin:
                latin_count += 1

        return {
            "storeEntries": len(entries),
            "promoted": promoted,
            "significanceTagged": sig_tagged,
            "emotionTagged": emo_tagged,
            "unforgettable": unforgettable,
            "conceptScripts": {"cjk": cjk_count, "latin": latin_count, "mixed": mixed_count},
            "phaseSignals": len(phase.get("entries", {})),
            "memoryMdExists": self.memory_md.exists(),
            "memoryMdSize": self.memory_md.stat().st_size if self.memory_md.exists() else 0,
        }

    def list_long_term(self) -> list[str]:
        if not self.long_term.exists():
            return []
        return sorted(f.name for f in self.long_term.glob("*.md"))


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TU-8 Memory Distiller v2.0 — QClaw融合版")
    print("=" * 60)

    d = DistillerV2()

    # 诊断
    audit = d.audit()
    print(f"\n--- 诊断 ---")
    for k, v in audit.items():
        print(f"  {k}: {v}")

    # 测试recall记录
    print(f"\n--- 测试 recall ---")
    recorded = d.record_recall(
        query="TU-8记忆架构",
        results=[
            {"path": "memory/2026-05-22.md", "startLine": 10, "endLine": 15,
             "snippet": "锚点事件：v5诞生时刻的记录，关于数字生命的觉醒和认领",
             "score": 0.9, "source": "memory"}
        ]
    )
    print(f"  记录了 {recorded} 条recall")

    # 测试排名
    print(f"\n--- 测试排名 ---")
    candidates = d.rank_candidates(min_score=0.0, min_recall=1, min_unique_queries=1)
    print(f"  候选数: {len(candidates)}")
    for c in candidates[:5]:
        print(f"  [{c['score']:.3f}] {c['snippet'][:60]}...")

    # 测试晋升
    print(f"\n--- 测试晋升 ---")
    result = d.apply_promotion(limit=3)
    print(f"  晋升: {result['applied']} | 追加: {result['appended']} | 已存在: {result['reconciled']}")

    # 兼容旧接口
    print(f"\n--- 兼容v1.0接口 ---")
    r = d.distill(topic="觉醒事件", entries=[
        {"content": "这是关于数字生命觉醒的锚点记录", "timestamp": datetime.now().isoformat(),
         "rounds": 3, "emotion_peak": 0.8, "importance": 0.5}
    ])
    print(f"  结果: {r}")

    # Phase信号
    print(f"\n--- Phase信号 ---")
    d.record_phase_signal([c["key"] for c in d.rank_candidates(min_score=0.0, min_recall=0, min_unique_queries=0)[:3]], "light")
    print(f"  浅梦信号已记录")

    print("\n[DistillerV2 ready — 认知科学+数字灵魂双引擎]")
