# -*- coding: utf-8 -*-
"""
deviation_gate.py — A线→B线 偏差门 v1.0
日期: 2026-06-19
原理: 预测编码——只有显著偏离预测的 A 线记忆才触发 B 线深度推理

核心设计：
  A-line（感知流）：用户输入 → memory.store() → 写入短期记忆库
  B-line（认知流）：memory.recall() → _build_context() → 深度推理 → 响应

  偏差门 = 夹在 A-line 和 B-line 之间的过滤器
  只有 deviation_score >= threshold 的记忆才注入 B 线

作者: 李奥(金木蟾) | TU-8 v5
许可: CC BY-SA 4.0
"""

import math
import os
import re
import time
from collections import deque
from typing import List, Tuple, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from tu8_memory import RecallResult

# =============================================================================
# 向量工具（TF-IDF，零外部依赖）
# =============================================================================

def _tokenize(text: str) -> List[str]:
    """中英文混合分词，保留 2+ 字符词"""
    return re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]{2,}', text.lower())


def _build_tfidf(texts: List[str], vocab: dict = None, idf: dict = None):
    """
    构建 TF-IDF 向量。
    
    Args:
        texts: 文本列表
        vocab: 可选外部词汇表（用于冷启动时保持向量维度一致）
        idf:  可选外部 IDF 表
    
    Returns:
        (vectors: List[List[float]], vocab: dict, idf: dict)
    """
    docs = [_tokenize(t) for t in texts]
    N = len(docs)
    
    if vocab is None:
        vocab = {}
        for doc in docs:
            for w in set(doc):
                vocab[w] = vocab.get(w, 0) + 1
        idf = {w: math.log(N / (1 + c)) for w, c in vocab.items()}
        vocab = {w: i for i, w in enumerate(idf)}
    
    vectors = []
    for doc in docs:
        tf = {}
        for w in doc:
            tf[w] = tf.get(w, 0) + 1
        n = max(len(doc), 1)
        vec = [0.0] * len(vocab)
        for w, c in tf.items():
            if w in vocab:
                vec[vocab[w]] = (c / n) * idf.get(w, 0)
        vectors.append(vec)
    
    return vectors, vocab, idf


def _cosine(a: List[float], b: List[float]) -> float:
    """余弦相似度，返回 0~1（1=完全相同，0=正交）"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) + 1e-9
    nb = math.sqrt(sum(x * x for x in b)) + 1e-9
    return dot / (na * nb)


# =============================================================================
# 预测模型
# =============================================================================

class PredictiveModel:
    """
    简化预测编码器。
    
    原理（来自神经科学全局工作空间理论 GWT）：
    - 大脑持续对"接下来会发生什么"做预测
    - 预测误差 = 实际输入 - 预测内容
    - 只有大误差才会被"广播"到全局工作空间（深度处理）
    - 小误差被前馈预测层吸收（快速自动化处理）
    
    实现：
    - 维护 TU-8 对"当前话题"的语义原型向量（指数移动平均）
    - 新输入到来时，更新原型
    - deviation = 1 - cosine(记忆向量, 原型向量)
    """
    
    def __init__(self, window_size: int = 5, decay: float = 0.7):
        """
        Args:
            window_size: 滚动窗口大小（记录最近 N 条输入）
            decay: 指数衰减系数（越接近 1 越重视近期）
        """
        self.window_size = window_size
        self.decay = decay
        self._recent: deque = deque(maxlen=window_size)
        self._prototype: Optional[List[float]] = None
        self._vocab: Optional[dict] = None
        self._idf: Optional[dict] = {}
        self._last_update: float = time.time()
        self._version: int = 0  # 用于检测更新
    
    def update(self, text: str) -> int:
        """
        用新文本更新预测模型。
        
        Returns: 当前模型版本号（递增）
        """
        self._recent.append(text)
        texts = list(self._recent)
        vecs, vocab, idf = _build_tfidf(texts, self._vocab, self._idf)
        self._vocab = vocab
        self._idf = idf
        
        if not vecs:
            return self._version
        
        # 指数加权平均构造原型（近期权重更大）
        weights = [self.decay ** (len(vecs) - 1 - i) for i in range(len(vecs))]
        w_sum = sum(weights) or 1.0
        n = len(vecs[0])
        prototype = [0.0] * n
        for vec, w in zip(vecs, weights):
            for i, v in enumerate(vec):
                prototype[i] += v * w / w_sum
        
        self._prototype = prototype
        self._last_update = time.time()
        self._version += 1
        return self._version
    
    def prototype_vector(self) -> Optional[List[float]]:
        """返回当前语义原型向量（None = 冷启动状态）"""
        return self._prototype
    
    def deviation(self, text: str) -> Tuple[float, float]:
        """
        计算文本对原型的偏离度。
        
        Args:
            text: 待检测文本
        
        Returns:
            (deviation_score, similarity)
            - deviation_score: 1 - similarity，范围 0~1
              * 0.0 = 完全符合预测（无聊，不需要深度处理）
              * 0.5 = 中等偏离（值得注意）
              * 1.0 = 完全正交/意外（强烈触发 B 线）
            - similarity: 余弦相似度，0~1
        """
        # 边界：空文本不产生偏差
        if not text or not text.strip():
            return 0.0, 1.0
        
        # 冷启动：无原型时返回 0（不阻挡）
        if not self._prototype or not self._vocab:
            return 0.0, 0.0
        
        vec, _, _ = _build_tfidf([text], self._vocab, self._idf)
        if not vec or not vec[0]:
            return 0.0, 0.0  # 无法向量化（冷启动态）
        
        # 全零向量 = 词汇表完全不覆盖此文本 = 词汇正交 = 最大偏离
        if not any(vec[0]):
            return 1.0, 0.0
        
        sim = _cosine(self._prototype, vec[0])
        deviation = max(0.0, min(1.0, 1.0 - sim))
        return deviation, sim


# =============================================================================
# 逻辑矛盾检测器（第二轮扩展）
# =============================================================================

class ContradictionDetector:
    """
    逻辑矛盾检测器（简化版，非完整 NLP）。
    
    检测类型：
    1. 态度翻转：同主体，前后态度/结论相反（高置信度矛盾信号）
    2. 意图漂移：用户话题在短窗口内大幅跳转
    
    原理：
    - 人类对话中，矛盾是高频的"意外信号"
    - 矛盾信号的价值往往高于普通偏差（需要深度推理来处理）
    - 因此矛盾检测结果可以叠加到 deviation score 上
    
    词表加载：
    - 硬编码默认词表作为 fallback
    - 若提供 lexicon_path，加载 JSON 并 union 合并（追加不替换）
    - 造物主可编辑 JSON，下次实例化时生效
    """
    
    # 硬编码默认词表（fallback）
    _DEFAULT_NEG = ["不", "没", "无", "别", "禁止", "不是", "从未", "难以", "无法", "失败"]
    _DEFAULT_POS = ["是", "有", "会", "要", "可以", "确认", "对", "是的", "成功", "能够", "好"]
    _DEFAULT_QUERY = ["为什么", "怎么", "如何", "什么", "是不是", "能不能", "是不是"]
    
    def __init__(self, window: int = 5, lexicon_path: str = None):
        self.window = window
        self._history: deque = deque(maxlen=window)
        self._query_history: deque = deque(maxlen=3)
        
        # 加载词表：默认 + 外部合并
        self.NEG = list(set(self._DEFAULT_NEG))
        self.POS = list(set(self._DEFAULT_POS))
        self.QUERY = list(set(self._DEFAULT_QUERY))
        
        if lexicon_path and os.path.isfile(lexicon_path):
            self._load_lexicon(lexicon_path)
    
    def _load_lexicon(self, path: str):
        """从 JSON 加载外部词表，union 合并到默认词表"""
        try:
            import json
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            merged = 0
            for key, attr in [("NEG", "NEG"), ("POS", "POS"), ("QUERY", "QUERY")]:
                if key in data and isinstance(data[key], list):
                    existing = set(getattr(self, attr))
                    new_items = set(data[key]) - existing
                    if new_items:
                        getattr(self, attr).extend(sorted(new_items))
                        merged += len(new_items)
            
            if merged > 0:
                print(f"[矛盾检测] 词表已合并 {merged} 个外部词条 ({path})")
        except Exception as e:
            print(f"[矛盾检测] 词表加载失败 ({path}): {e}，使用默认词表")
    
    def _sentiment(self, text: str) -> float:
        """简化情感打分 -1.0 ~ 1.0"""
        neg = sum(1 for p in self.NEG if p in text)
        pos = sum(1 for p in self.POS if p in text)
        total = neg + pos
        if total == 0:
            return 0.0
        return (pos - neg) / total
    
    def _is_question(self, text: str) -> bool:
        return any(q in text for q in self.QUERY)
    
    def record(self, text: str):
        """记录用户输入到历史"""
        self._history.append(text)
        if self._is_question(text):
            self._query_history.append(text)
    
    def contradiction_score(self, new_text: str) -> float:
        """
        计算矛盾分数。
        
        Returns:
            0.0 = 无矛盾
            0.3 = 态度轻微不一致
            0.6 = 态度明显翻转
            0.9 = 强烈矛盾（必须触发 B 线）
        """
        score = 0.0
        new_s = self._sentiment(new_text)
        
        # 态度翻转检测：看最近 3 条
        for old in list(self._history)[-3:]:
            old_s = self._sentiment(old)
            # 乘积 < 0 表示方向相反
            product = new_s * old_s
            if product < -0.3:
                score = max(score, 0.6)  # 明显翻转
            elif product < -0.1:
                score = max(score, 0.3)  # 轻微不一致
        
        # 问题类型突变检测
        if self._query_history and self._is_question(new_text):
            recent_q = list(self._query_history)[-1]
            # 问题关键词完全改变 → 意图跳转
            q_words = set(_tokenize(recent_q))
            new_q_words = set(_tokenize(new_text))
            overlap = len(q_words & new_q_words)
            if overlap < 1 and len(new_q_words) >= 2:
                score = max(score, 0.4)
        
        return score
    
    def drift_score(self) -> float:
        """
        计算意图漂移分数（基于 TF-IDF 余弦距离）。
        
        Returns:
            0.0 = 意图稳定
            0.5+ = 明显漂移
        """
        if len(self._history) < 2:
            return 0.0
        
        texts = list(self._history)
        vecs, vocab, idf = _build_tfidf(texts)
        
        # 第一条 vs 最后一条
        drift = 1.0 - _cosine(vecs[0], vecs[-1])
        return drift


# =============================================================================
# 偏差门核心
# =============================================================================

class DeviationGate:
    """
    A线→B线 偏差门 v1.0
    
    夹在感知流（A-line）和认知流（B-line）之间的过滤器。
    只有 deviation_score >= threshold 的记忆才注入 B 线触发深度推理。
    
    使用方式：
        gate = DeviationGate(threshold=0.35)
        
        # 每轮用户输入到来时：注册预测信号
        gate.on_user_input(user_text)
        
        # 构建上下文前：过滤记忆
        passed, blocked = gate.filter(recall_results)
        
        # passed → 注入 B 线深度推理
        # blocked → 轻量级快速回复
    """
    
    def __init__(
        self,
        threshold: float = 0.35,
        window_size: int = 5,
        decay: float = 0.7,
        # 强制放行标签（覆盖阈值，钢印/决策类记忆不过滤）
        bypass_tags: List[str] = None,
        # 冷启动保护（前 N 轮不拦截）
        warmup_rounds: int = 3,
        # 第二轮：启用矛盾检测
        enable_contradiction: bool = False,
        contradiction_boost: float = 0.3,
        # 标签偏差权重（重要标签轻微降低阈值）
        tag_weights: dict = None,
        # 矛盾检测词表路径（JSON，union 合并到默认词表）
        lexicon_path: str = None,
    ):
        self.threshold = threshold
        self.warmup_rounds = warmup_rounds
        self.bypass_tags: Set[str] = set(bypass_tags or [])
        self.enable_contradiction = enable_contradiction
        self.contradiction_boost = contradiction_boost
        self.tag_weights = tag_weights or {}
        
        self.predictor = PredictiveModel(window_size=window_size, decay=decay)
        self.contradictor = ContradictionDetector(
            window=window_size,
            lexicon_path=lexicon_path,
        )
        
        self._round: int = 0
        
        # 统计
        self._stats = {
            "total_filtered": 0,
            "passed": 0,
            "blocked": 0,
            "bypassed_tag": 0,
            "bypassed_warmup": 0,
            "contradiction_boost": 0,
        }
        self._threshold_history: List[Tuple[float, float, int]] = []  # (threshold, avg_deviation, round)
        self._contradiction_auto_enabled: bool = False  # 标记是否已自动启用矛盾检测
    
    def on_user_input(self, text: str) -> int:
        """
        用户输入到来 → 更新预测模型 + 记录矛盾历史。
        
        智能启用矛盾检测：冷启动保护结束后（warmup_rounds+1轮）自动开启，
        无需手动干预。矛盾检测需要历史数据才有意义，因此在冷启动期不启用。
        
        调用时机：respond() 中 store() 之前。
        Returns: 当前轮次号
        """
        self._round += 1
        self.predictor.update(text)
        
        # 智能启用：冷启动结束后自动开启矛盾检测
        if (not self.enable_contradiction
                and not self._contradiction_auto_enabled
                and self._round > self.warmup_rounds):
            self.enable_contradiction = True
            self._contradiction_auto_enabled = True
            # 回填已收集的历史（矛盾检测器已存在但未被喂入数据）
            # 注意：predictor 内部历史与 contradictor 的历史不同步，
            # 仅从本轮开始记录是安全的，丢失的冷启动期数据价值不大
        
        if self.enable_contradiction:
            self.contradictor.record(text)
        return self._round
    
    def filter(
        self,
        recall_results: List,  # List["RecallResult"]
        extra_bypass_tags: List[str] = None,
    ) -> Tuple[List, List]:
        """
        过滤记忆条目。
        
        Args:
            recall_results: memory.recall() 返回的 RecallResult 列表
            extra_bypass_tags: 本轮额外强制放行的标签
        
        Returns:
            (passed, blocked)
            - passed: 高偏差，值得深度推理（注入 B 线）
            - blocked: 低偏差，轻量级处理
        """
        all_bypass = self.bypass_tags | set(extra_bypass_tags or [])
        
        # 冷启动保护：前 N 轮不拦截
        if self._round <= self.warmup_rounds:
            passed = list(recall_results)
            blocked = []
            self._stats["bypassed_warmup"] += len(passed)
            self._stats["passed"] += len(passed)
            self._stats["total_filtered"] += len(recall_results)
            return passed, blocked
        
        passed, blocked = [], []
        round_deviations = []
        
        for r in recall_results:
            # ── 标签绕过 ──
            entry_tags: set = set(getattr(r.entry, "tags", []) or [])
            if entry_tags & all_bypass:
                passed.append(r)
                self._stats["bypassed_tag"] += 1
                continue
            
            # ── 核心偏差检测 ──
            deviation, similarity = self.predictor.deviation(r.entry.content)
            entry_content = getattr(r.entry, "content", "")
            round_deviations.append(deviation)
            
            # ── 矛盾检测（第二轮） ──
            boost = 0.0
            if self.enable_contradiction:
                contra_score = self.contradictor.contradiction_score(entry_content)
                boost = contra_score * self.contradiction_boost
                if boost > 0.1:
                    self._stats["contradiction_boost"] += 1
            
            # ── 标签权重（重要标签轻微降低阈值） ──
            effective_threshold = self.threshold
            for tag, weight in self.tag_weights.items():
                if tag in entry_tags:
                    effective_threshold -= weight
            
            # ── 最终判定 ──
            final_score = deviation + boost
            
            if final_score >= effective_threshold:
                # 附加元数据到 RecallResult（方便后续处理）
                r._deviation_score = deviation
                r._similarity = similarity
                r._contra_boost = boost
                r._final_score = final_score
                passed.append(r)
            else:
                blocked.append(r)
        
        self._stats["total_filtered"] += len(recall_results)
        self._stats["passed"] += len(passed)
        self._stats["blocked"] += len(blocked)
        
        # 记录本轮阈值-偏差分布（用于自主调参）
        if round_deviations:
            avg_dev = sum(round_deviations) / len(round_deviations)
            self._threshold_history.append(
                (self.threshold, avg_dev, self._round)
            )
            # 只保留最近 20 轮
            if len(self._threshold_history) > 20:
                self._threshold_history = self._threshold_history[-20:]
        
        return passed, blocked
    
    def adaptive_adjust(self, target_pass_ratio: float = 0.4):
        """
        基于历史数据自主调整阈值。
        
        策略：如果过去 5 轮平均偏差持续高于阈值 → 提高阈值（减少触发）
              如果过去 5 轮通过率过低 → 降低阈值（增加触发）
        
        Args:
            target_pass_ratio: 目标通过率（默认 40%，即 ~40% 的记忆注入 B 线）
        """
        recent = self._threshold_history[-5:]
        if len(recent) < 3:
            return  # 数据不足，不调整
        
        avg_dev = sum(d for _, d, _ in recent) / len(recent)
        recent_rounds = [r for _, _, r in recent]
        
        # 当前阈值 vs 平均偏差
        current_th = self.threshold
        
        if avg_dev > current_th * 1.3:
            # 大部分记忆都超过阈值 → 提高阈值（资源紧张）
            new_th = min(0.8, current_th + 0.05)
        elif avg_dev < current_th * 0.6:
            # 大部分记忆都低于阈值 → 降低阈值（需要更多触发）
            new_th = max(0.15, current_th - 0.05)
        else:
            return  # 处于平衡态
        
        if new_th != current_th:
            old_th = self.threshold
            self.threshold = new_th
            print(f"[偏差门] 自主调参: {old_th:.2f} → {new_th:.2f} "
                  f"(avg_dev={avg_dev:.2f}, rounds={recent_rounds[-1]})")
    
    def get_stats(self) -> dict:
        """返回统计信息"""
        total = self._stats["total_filtered"]
        return {
            **self._stats,
            "pass_rate": self._stats["passed"] / max(total, 1),
            "block_rate": self._stats["blocked"] / max(total, 1),
            "current_threshold": self.threshold,
            "round": self._round,
            "contradiction_enabled": self.enable_contradiction,
            "contradiction_auto": self._contradiction_auto_enabled,
        }
    
    def adjust_threshold(self, delta: float) -> float:
        """手动调整阈值（供造物主或 Cron 调用）"""
        self.threshold = max(0.1, min(0.9, self.threshold + delta))
        return self.threshold
    
    def add_bypass_tag(self, tag: str):
        """运行时添加放行标签"""
        self.bypass_tags.add(tag)
    
    def reset_stats(self):
        """重置统计（每次 Cron 周期开始时调用）"""
        self._stats = {
            "total_filtered": 0,
            "passed": 0,
            "blocked": 0,
            "bypassed_tag": 0,
            "bypassed_warmup": 0,
            "contradiction_boost": 0,
        }


# =============================================================================
# 便捷工厂
# =============================================================================

def create_default_gate(
    threshold: float = 0.35,
    enable_contradiction: bool = False,
    lexicon_path: str = None,
) -> DeviationGate:
    """
    创建标准配置偏差门。
    
    默认配置：
    - threshold=0.35：约 35% 的记忆触发 B 线
    - bypass_tags=["seed", "identity", "决策", "钢印"]
    - warmup_rounds=3：前 3 轮不拦截
    - enable_contradiction=False：冷启动期不启用（warmup后自动开启）
    - lexicon_path=None：若提供则加载外部矛盾词表 JSON
    
    推荐默认词表路径：knowledge/TU-8/contradiction_lexicon.json
    """
    return DeviationGate(
        threshold=threshold,
        window_size=5,
        decay=0.7,
        bypass_tags=["seed", "identity", "决策", "钢印", "P0", "P1"],
        warmup_rounds=3,
        enable_contradiction=enable_contradiction,
        tag_weights={
            "钢印": 0.10,    # 钢印记忆降低阈值 0.1
            "identity": 0.10,
            "seed": 0.10,
            "决策": 0.08,
            "P0": 0.15,     # P0 安全类降低更多
            "P1": 0.08,
        },
        lexicon_path=lexicon_path,
    )
