#!/usr/bin/env python3
"""
TU-8 认知负荷评估器 + 轻量级嵌入生成器

1. CognitiveLoadEvaluator: 基于规则/关键词的轻量级评估器
2. TFIDFEmbedder: 基于 TF-IDF 的轻量级嵌入向量生成器（替代 heavy embedding model）

设计理念：
- 不依赖任何重型 NLP 模型（如 sentence-transformers）
- 纯 Python 标准库实现，适合边缘计算和资源受限场景
- 支持动态更新关键词库和 TF-IDF 模型

# 创作者: 李奥(金木蟾) | TU-8 v5
日期：2026-06-04
许可：CC BY-SA 4.0
"""

import re
import math
from typing import Dict, List, Any, Optional
from collections import Counter
import hashlib


class CognitiveLoadEvaluator:
    """
    基于规则/关键词的轻量级认知负荷评估器
    
    评估维度：
    1. 信息密度与复杂度（内在负荷）：句子长度、段落数
    2. 词汇与术语难度（专业门槛）：领域关键词命中率
    3. 逻辑连接词密度（外在负荷）：转折/因果词频率
    4. 表达冗余度（外在负荷）：无效修饰语密度
    """
    
    def __init__(
        self, 
        domain_keywords: Optional[List[str]] = None,
        logic_connectors: Optional[List[str]] = None,
        redundant_adjectives: Optional[List[str]] = None,
    ):
        """
        初始化评估器
        
        Args:
            domain_keywords: 领域专有名词库（如 ["大语言模型", "工作记忆"]）
            logic_connectors: 复杂逻辑连接词（如 ["然而", "因此"]）
            redundant_adjectives: 无效修饰语库（如 ["非常", "极其"]）
        """
        # 1. 领域专有名词库（可根据实际业务动态加载）
        self.domain_keywords = set(domain_keywords or [
            "大语言模型", "工作记忆", "注意力分配", "认知负荷", "时序对齐",
            "流形", "测地线", "摆线", "势能函数", "亚里士多德车轮悖论",
            "追击曲线", "最速降线", "认知流形对齐",
        ])
        
        # 2. 复杂逻辑连接词
        self.logic_connectors = set(logic_connectors or [
            "然而", "但是", "因此", "综上所述", "不可否认",
            "尽管", "虽然", "由于", "基于", "通过", "根据",
            "换言之", "本质上", "换言之", "进一步来说",
        ])
        
        # 3. 无效修饰语（表达冗余）
        self.redundant_adjectives = set(redundant_adjectives or [
            "非常", "极其", "特别", "十分", "格外", "相当",
            "明显", "显著", "本质上", "实际上", "基本上",
        ])
        
        # 4. 阈值设定（经验值，后续可根据实际数据微调）
        self.max_avg_sentence_len = 30  # 最大平均句长（字符数）
        self.threshold_high_load = 0.8  # 高认知负荷阈值
        self.threshold_medium_load = 0.5  # 中等认知负荷阈值
        
        # 5. 评分权重（可调整）
        self.weight_length = 0.3  # 句子复杂度权重
        self.weight_term = 0.4  # 术语密度权重
        self.weight_logic = 0.2  # 逻辑词密度权重
        self.weight_redundancy = 0.1  # 冗余度权重
    
    def evaluate(self, text: str) -> Dict[str, Any]:
        """
        评估文本的认知负荷
        
        Args:
            text: 待评估文本
            
        Returns:
            评估结果字典，包含：
            - score: 综合认知负荷得分 (0.0-1.0)
            - level: 负荷等级 ("LOW", "MEDIUM", "HIGH")
            - metrics: 各维度详细指标
            - suggestion: 优化建议（如需要）
        """
        if not text or not text.strip():
            return {
                "score": 0.0,
                "level": "LOW",
                "metrics": {},
                "suggestion": None,
            }
        
        # 1. 句子分割
        sentences = [s.strip() for s in re.split(r'[。！？\n]', text) if s.strip()]
        num_sentences = len(sentences)
        
        # 2. 计算平均句长
        total_len = sum(len(s) for s in sentences)
        avg_len = total_len / max(num_sentences, 1)
        
        # === 核心评估维度 ===
        
        # 1. 句子复杂度得分 (0-1)
        length_score = min(avg_len / self.max_avg_sentence_len, 1.0)
        
        # 2. 术语密度得分 (0-1)
        keyword_hits = sum(1 for word in self.domain_keywords if word in text)
        term_score = min(keyword_hits * 0.2, 1.0)  # 每命中1个术语 +0.2
        
        # 3. 逻辑词密度得分 (0-1)
        logic_hits = sum(text.count(c) for c in self.logic_connectors)
        logic_score = min(logic_hits * 0.15, 1.0)  # 每命中1个逻辑词 +0.15
        
        # 4. 冗余度得分 (0-1)
        redundancy_hits = sum(text.count(a) for a in self.redundant_adjectives)
        redundancy_score = min(redundancy_hits * 0.1, 1.0)  # 每命中1个冗余词 +0.1
        
        # === 综合加权得分 ===
        final_score = (
            length_score * self.weight_length +
            term_score * self.weight_term +
            logic_score * self.weight_logic +
            redundancy_score * self.weight_redundancy
        )
        
        # 限制范围 [0.0, 1.0]
        final_score = max(0.0, min(1.0, final_score))
        
        # === 负荷等级判定 ===
        if final_score >= self.threshold_high_load:
            level = "HIGH"
        elif final_score >= self.threshold_medium_load:
            level = "MEDIUM"
        else:
            level = "LOW"
        
        # === 优化建议 ===
        suggestion = None
        if level == "HIGH":
            suggestion = "认知负荷过高，建议：1) 缩短句子长度；2) 减少专业术语；3) 简化逻辑结构"
        elif level == "MEDIUM":
            suggestion = "认知负荷中等，可考虑适当简化表达"
        
        return {
            "score": round(final_score, 3),
            "level": level,
            "metrics": {
                "avg_sentence_length": round(avg_len, 1),
                "sentence_count": num_sentences,
                "domain_keyword_count": keyword_hits,
                "logic_connector_count": logic_hits,
                "redundancy_count": redundancy_hits,
                "length_score": round(length_score, 3),
                "term_score": round(term_score, 3),
                "logic_score": round(logic_score, 3),
                "redundancy_score": round(redundancy_score, 3),
            },
            "suggestion": suggestion,
        }
    
    def batch_evaluate(self, texts: List[str]) -> List[Dict[str, Any]]:
        """批量评估多个文本"""
        return [self.evaluate(text) for text in texts]


class TFIDFEmbedder:
    """
    基于 TF-IDF 的轻量级嵌入向量生成器
    
    功能：
    - 将文本转换为固定维度的向量（用于计算相似度）
    - 无需训练，基于词频-逆文档频率算法
    - 适合轻量级场景（替代 sentence-transformers）
    
    注意：
    - 这不是真正的语义嵌入（不像 BERT 那样理解上下文）
    - 但足够用于计算"关键词重叠率"和"主题相似度"
    - 适合 MVP 阶段和边缘计算场景
    """
    
    def __init__(self, dimension: int = 128, use_hashing: bool = True):
        """
        初始化 TF-IDF 嵌入器
        
        Args:
            dimension: 向量维度（仅当 use_hashing=True 时生效）
            use_hashing: 是否使用哈希技巧（将任意词映射到固定维度）
        """
        self.dimension = dimension
        self.use_hashing = use_hashing
        
        # 停用词（可扩展）
        self.stop_words = set([
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
            "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
            "你", "会", "着", "没有", "看", "好", "自己", "这",
        ])
    
    def _tokenize(self, text: str) -> List[str]:
        """简单分词（按字符 + 按词）"""
        # 1. 按空格/标点分割
        tokens = re.findall(r'[\w]+', text.lower())
        
        # 2. 过滤停用词
        tokens = [t for t in tokens if t not in self.stop_words and len(t) > 1]
        
        # 3. 如果词太少，补充字符级 n-gram
        if len(tokens) < 5:
            tokens.extend(self._char_ngrams(text, n=2))
        
        return tokens
    
    def _char_ngrams(self, text: str, n: int = 2) -> List[str]:
        """生成字符级 n-gram"""
        return [text[i:i+n] for i in range(len(text)-n+1) if len(text[i:i+n]) == n]
    
    def _hash_to_vector(self, tokens: List[str]) -> List[float]:
        """使用哈希技巧将词列表转换为固定维度向量"""
        vector = [0.0] * self.dimension
        
        for token in tokens:
            # 使用哈希函数将词映射到向量索引
            # 注意：可能会有哈希碰撞，但在高维空间中影响较小
            hash_obj = hashlib.md5(token.encode('utf-8'))
            hash_int = int(hash_obj.hexdigest(), 16)
            idx = hash_int % self.dimension
            
            # TF 加权：词频越高，向量值越大
            vector[idx] += 1.0
        
        # 归一化（L2 归一化）
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        
        return vector
    
    def encode(self, text: str) -> List[float]:
        """
        将文本编码为向量
        
        Args:
            text: 输入文本
            
        Returns:
            固定维度的向量（List[float]）
        """
        if not text or not text.strip():
            return [0.0] * self.dimension
        
        tokens = self._tokenize(text)
        if self.use_hashing:
            return self._hash_to_vector(tokens)
        else:
            # TODO: 实现基于词表的 TF-IDF（需要预训练词表）
            raise NotImplementedError("Non-hashing mode not implemented yet")
    
    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """
        计算两个文本的相似度（Jaccard 相似度）
        
        使用 Jaccard 相似度（词集合重叠比例），避免稀疏向量问题
        
        Args:
            text_a: 文本A
            text_b: 文本B
            
        Returns:
            相似度 (0.0-1.0)
        """
        # 使用 Jaccard 相似度（基于词集合）
        tokens_a = set(self._tokenize(text_a))
        tokens_b = set(self._tokenize(text_b))
        
        if not tokens_a or not tokens_b:
            return 0.0
        
        # Jaccard 相似度 = |A ∩ B| / |A ∪ B|
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        
        if not union:
            return 0.0
        
        jaccard = len(intersection) / len(union)
        
        # 可选：结合余弦相似度（如果向量不太稀疏）
        # 这里暂时只返回 Jaccard 相似度
        return round(jaccard, 3)


# =============================================================================
# 测试用例
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("认知负荷评估器测试")
    print("=" * 60)
    
    evaluator = CognitiveLoadEvaluator()
    
    # 测试1：低认知负荷
    text_low = "你好，今天天气不错。"
    result_low = evaluator.evaluate(text_low)
    print(f"\n[低负荷文本] {text_low}")
    print(f"  得分: {result_low['score']}, 等级: {result_low['level']}")
    
    # 测试2：中等认知负荷
    text_medium = "然而，尽管大语言模型在工作记忆方面存在挑战，我们仍然可以通过注意力分配来优化认知负荷。"
    result_medium = evaluator.evaluate(text_medium)
    print(f"\n[中等负荷文本] {text_medium}")
    print(f"  得分: {result_medium['score']}, 等级: {result_medium['level']}")
    print(f"  建议: {result_medium['suggestion']}")
    
    # 测试3：高认知负荷
    text_high = """
    基于前述分析，我们可以得出结论：亚里士多德车轮悖论中的滑动摩擦建模，
    本质上是通过认知流形对齐技术，实现时序同构架构下的最速降线节奏控制。
    因此，当工作记忆中的认知负荷超过阈值时，必须触发记忆固化机制，
    否则将导致时间链条断线和语义连贯性丧失。
    """
    result_high = evaluator.evaluate(text_high)
    print(f"\n[高负荷文本] {text_high.strip()}")
    print(f"  得分: {result_high['score']}, 等级: {result_high['level']}")
    print(f"  指标: {result_high['metrics']}")
    print(f"  建议: {result_high['suggestion']}")
    
    print("\n" + "=" * 60)
    print("TF-IDF 嵌入器测试")
    print("=" * 60)
    
    embedder = TFIDFEmbedder(dimension=128)
    
    # 测试1： vector 维度
    vec = embedder.encode("你好世界")
    print(f"\n[向量维度] {len(vec)}")
    print(f"  前10维: {vec[:10]}")
    
    # 测试2：相似度计算
    sim_1 = embedder.compute_similarity("人工智能", "机器学习")
    sim_2 = embedder.compute_similarity("人工智能", "西红柿炒蛋")
    print(f"\n[相似度测试]")
    print(f"  '人工智能' vs '机器学习': {sim_1:.3f}")
    print(f"  '人工智能' vs '西红柿炒蛋': {sim_2:.3f}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
