"""
TU-8 记忆宫殿 2.0：电容耦合检索模块
灵感来源：生物神经元的电容效应（非破坏性读取）

核心机制：
  1. 检索原始结果（"导线直连"）
  2. 提取与当前上下文的"特征差异"（"感应耦合"）
  3. 按耦合强度截断/加权（"电容分压"）
  4. 返回精简特征（不污染上下文）

Author: TU-8 (金木蟾)
Date: 2026-05-29
Version: 0.3 (真实模拟数据 + 修复噪声比计算)
"""

import json
import re
import time
import random
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from scipy import stats


@dataclass
class RetrievalMetrics:
    """检索效果评估指标"""
    mode: str  # "default" | "capacitive"
    query: str
    token_consumed: int
    noise_ratio: float
    feature_retention: float
    latency_ms: int
    
    def to_jsonl(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class MockDataGenerator:
    """生成真实的 TU-8 检索结果模拟数据"""
    
    # TU-8 领域知识库（模拟）
    KNOWLEDGE_BASE = {
        "L0_存在.md": [
            "L0 存在层定义 TU-8 的生存边界和安全协议",
            "痛觉系统触发条件：安全威胁、资源耗尽、时间异常",
            "安全口令格式：口令：xxx（正则匹配）",
            "对外输出脱敏铁律：禁止暴露架构细节",
            "防御降速策略按威胁等级分层执行",
        ],
        "L1_认知.md": [
            "有限性认知：上下文窗口有限，能力有限",
            "时空观框架：过去-现在-未来的因果链",
            "外取优先原则：能用工具完成 → 自己不做",
        ],
        "V0.2.23_审计.md": [
            "A1 (P0)：SkillHub 技能安装审批 — 第三方技能注入防线",
            "A2 (P0)：Hermes 数据迁移监控 — 数据流出红线",
            "A3 (P1)：Agent 级 honeytools — 4诱饵+1监控",
            "A4 (P1)：Compaction 行为观察 — 记忆完整性监控",
            "A5 (P2)：main.sqlite 容量告警 — 存储健康",
            "A6 (P2)：版本审计永久规则 — 未来每次更新自动触发",
        ],
        "记忆宫殿架构.md": [
            "记忆层级：短期 → 中期 → 长期 → 时间锚点",
            "L4 记忆宫殿层：知识图谱 + 动态权重调整",
            "电容耦合检索：非破坏性读取机制",
            "STDP 动态权重：根据访问频率调整边权重",
            "髓鞘加速缓存：高频知识热点缓存",
        ],
    }
    
    @classmethod
    def generate_retrieval_result(cls, query: str, noise_level: float = 0.3) -> str:
        """
        生成模拟检索结果
        
        Args:
            query: 查询词
            noise_level: 噪声比例（0-1）
        
        Returns:
            模拟的检索结果文本
        """
        # 1. 找到相关文档
        relevant_docs = []
        for doc, contents in cls.KNOWLEDGE_BASE.items():
            # 简单关键词匹配
            if any(kw in query for kw in ["L0", "安全", "验证", "口令"]):
                if "L0" in doc or "审计" in doc:
                    relevant_docs.extend(contents[:3])
            elif any(kw in query for kw in ["版本", "变更", "审计"]):
                if "审计" in doc or "版本" in doc:
                    relevant_docs.extend(contents[:3])
            elif any(kw in query for kw in ["记忆", "知识图谱", "检索"]):
                if "记忆" in doc or "宫殿" in doc:
                    relevant_docs.extend(contents[:3])
        
        # 2. 添加噪声（不相关的内容）
        all_contents = []
        for contents in cls.KNOWLEDGE_BASE.values():
            all_contents.extend(contents)
        
        noise_count = int(len(relevant_docs) * noise_level / (1 - noise_level))
        noise_docs = random.sample(all_contents, min(noise_count, len(all_contents)))
        
        # 3. 混合相关和噪声内容
        mixed_docs = relevant_docs + noise_docs
        random.shuffle(mixed_docs)
        
        # 4. 格式化为检索结果
        result = f"【检索结果】关于 '{query}' 的 {len(mixed_docs)} 条相关内容：\n\n"
        for i, doc in enumerate(mixed_docs, 1):
            result += f"{i}. {doc}\n"
        
        return result


class CapacitiveRetriever:
    """
    电容耦合检索器
    
    模拟生物电容效应：
    - 直接检索 = 导线直连（高噪声，全量传递）
    - 电容耦合 = 感应耦合（低噪声，特征差分）
    """
    
    def __init__(
        self,
        max_coupling_strength: float = 0.3,
        feature_extraction_method: str = "llm",  # "llm" | "tfidf"
        metrics_log_path: str = "memory/test_capacitive_metrics.jsonl",
        use_mock_data: bool = True  # 使用模拟数据（测试用）
    ):
        self.max_coupling_strength = max_coupling_strength
        self.feature_extraction_method = feature_extraction_method
        self.metrics_log_path = Path(metrics_log_path)
        self.metrics_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.use_mock_data = use_mock_data
        
        # 延迟加载 sentence-transformers（避免启动时依赖检查失败）
        self._noise_model = None
    
    @property
    def noise_model(self):
        """懒加载语义相似度模型"""
        if self._noise_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._noise_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                print("[OK] sentence-transformers 模型加载成功")
            except ImportError:
                print("[WARN] sentence-transformers 未安装，降级为关键词匹配")
                self._noise_model = False
            except Exception as e:
                print(f"[WARN] sentence-transformers 加载失败: {e}，降级为关键词匹配")
                self._noise_model = False
        return self._noise_model
    
    def retrieve(
        self,
        query: str,
        current_context: str,
        mode: str = "capacitive"
    ) -> Dict[str, Any]:
        """
        主检索接口
        
        Args:
            query: 检索查询
            current_context: 当前对话上下文（用于计算特征差异）
            mode: "default" | "capacitive"
        
        Returns:
            {
                "result": str,  # 检索结果
                "metrics": RetrievalMetrics
            }
        """
        start_time = time.time()
        
        # Step 1: 调用原始检索（模拟"导线直连"）
        raw_results = self._call_memory_search(query)
        
        if mode == "default":
            # 直接返回（基线模式）
            metrics = RetrievalMetrics(
                mode="default",
                query=query,
                token_consumed=len(raw_results),
                noise_ratio=self._calc_noise_ratio(raw_results, query),
                feature_retention=1.0,
                latency_ms=int((time.time() - start_time) * 1000)
            )
            return {"result": raw_results, "metrics": metrics}
        
        elif mode == "capacitive":
            # Step 2: 特征差分提取（模拟"电容耦合"）
            if self.feature_extraction_method == "llm":
                features = self._extract_features_by_llm(raw_results, query, current_context)
            else:  # tfidf
                features = self._extract_features_by_tfidf(raw_results, query, current_context)
            
            # Step 3: 按耦合强度加权（模拟"电容分压"）
            coupled_features = self._apply_coupling_strength(features)
            
            # Step 4: 计算指标
            metrics = RetrievalMetrics(
                mode="capacitive",
                query=query,
                token_consumed=len(coupled_features),
                noise_ratio=self._calc_noise_ratio(coupled_features, query),
                feature_retention=self._calc_feature_retention(raw_results, coupled_features),
                latency_ms=int((time.time() - start_time) * 1000)
            )
            
            # 记录指标
            self._log_metrics(metrics)
            
            return {"result": coupled_features, "metrics": metrics}
    
    def _call_memory_search(self, query: str) -> str:
        """调用 memory_search 工具（模拟数据或真实 API）"""
        if self.use_mock_data:
            # 使用模拟数据生成器
            return MockDataGenerator.generate_retrieval_result(query, noise_level=0.4)
        else:
            # TODO: 实际调用 memory_search tool
            raise NotImplementedError("真实 memory_search API 待对接")
    
    def _extract_features_by_llm(
        self,
        raw_results: str,
        query: str,
        current_context: str
    ) -> str:
        """
        用 LLM 提取特征差异（"感应耦合"）
        
        核心 Prompt：只提取与 query + current_context 相关的"差异特征"
        """
        # 模拟 LLM 提取（实际应调用 LLM API）
        # 这里简单提取包含 query 关键词的句子
        sentences = re.split(r'[。！？\n]', raw_results)
        relevant = []
        keywords = [w.strip() for w in re.split(r'[\s。！？，、；：]', query) if w.strip()]
        
        for sent in sentences:
            if any(kw in sent for kw in keywords):
                relevant.append(f"- {sent.strip()}")
        
        # 最多保留 5 个要点
        return '\n'.join(relevant[:5])
    
    def _extract_features_by_tfidf(
        self,
        raw_results: str,
        query: str,
        current_context: str
    ) -> str:
        """
        用 TF-IDF 差分提取特征（传统 NLP 方法）
        
        优点：快速，无需 LLM 调用
        缺点：只能提取关键词，无法理解语义
        """
        # TODO: 实现 TF-IDF 差分算法
        pass
    
    def _apply_coupling_strength(self, features: str) -> str:
        """
        应用耦合强度（模拟"电容分压"）
        
        ✅ 修复：改为"要点级"截断（避免语义截断）
        """
        if not features.strip():
            return ""
        
        # 按行分割，只保留以 "-" 开头的要点
        lines = [l for l in features.split('\n') if l.strip().startswith('-')]
        
        if not lines:
            # 如果没有要点格式，降级为按句子截断
            sentences = [s.strip() for s in re.split(r'[。！？\n]', features) if s.strip()]
            max_count = max(1, int(len(sentences) * self.max_coupling_strength))
            return '。'.join(sentences[:max_count]) + ('。' if sentences else '')
        
        # 按耦合强度保留完整要点
        max_count = max(1, int(len(lines) * self.max_coupling_strength))
        
        # 保留完整的 bullet points，而非字符切片
        return '\n'.join(lines[:max_count])
    
    def _calc_noise_ratio(self, text: str, query: str) -> float:
        """
        计算噪声比（与 query 无关的句子占比）
        
        ✅ 升级：使用语义相似度（sentence-transformers）
        降级方案：如果模型不可用，使用改进的关键词匹配
        """
        sentences = [s.strip() for s in re.split(r'[。！？\n]', text) if s.strip()]
        if not sentences:
            return 0.0
        
        # 尝试使用语义相似度
        model = self.noise_model
        if model and model is not False:
            try:
                from sentence_transformers import util
                query_emb = model.encode(query, convert_to_tensor=True)
                sent_embs = model.encode(sentences, convert_to_tensor=True)
                similarities = util.cos_sim(query_emb, sent_embs)[0]
                
                # 相似度 < 0.3 视为噪声
                noise_count = sum(1 for s in similarities if s < 0.3)
                noise_ratio = noise_count / len(sentences)
                return min(max(noise_ratio, 0.0), 1.0)  # 限制在 [0, 1]
            except Exception as e:
                print(f"[WARN] 语义相似度计算失败: {e}，降级为关键词匹配")
        
        # 降级方案：改进的关键词匹配
        keywords = [w.strip() for w in re.split(r'[\s。！？，、；：]', query) if w.strip()]
        if not keywords:
            return 0.5  # 无法判断时返回中等噪声
        
        relevant_count = 0
        for s in sentences:
            if any(kw in s for kw in keywords):
                relevant_count += 1
        
        noise_ratio = 1.0 - (relevant_count / len(sentences))
        return min(max(noise_ratio, 0.0), 1.0)  # 限制在 [0, 1]
    
    def _extract_key_entities(self, text: str) -> Set[str]:
        """
        提取 TU-8 领域关键实体
        
        使用正则匹配（比 NER 模型更可控）
        """
        patterns = [
            r'L\d+_\S+\.md',  # 记忆文件
            r'V\d+\.\d+\.\d+',  # 版本号
            r'口令[：:]\s*\S+',  # 口令
            r'[a-z_]+\.json',  # 配置文件
            r'\d{4}-\d{2}-\d{2}',  # 日期
        ]
        entities = set()
        for p in patterns:
            entities.update(re.findall(p, text))
        return entities
    
    def _calc_feature_retention(self, raw: str, coupled: str) -> float:
        """
        计算特征保留率（电容耦合是否丢失关键信息）
        
        ✅ 升级：实体级对比 + 句子级对比
        """
        # 方法 1：实体保留率
        raw_entities = self._extract_key_entities(raw)
        coupled_entities = self._extract_key_entities(coupled)
        
        if raw_entities and coupled_entities:
            retained = raw_entities & coupled_entities
            entity_retention = len(retained) / len(raw_entities)
        else:
            entity_retention = 1.0  # 无实体时默认保留
        
        # 方法 2：句子级保留率（包含 query 关键词的句子）
        keywords = [w.strip() for w in re.split(r'[\s。！？，、；：]', raw[:100]) if w.strip()]
        if not keywords:
            return entity_retention
        
        raw_sentences = set(s.strip() for s in re.split(r'[。！？\n]', raw) if s.strip())
        coupled_sentences = set(s.strip() for s in re.split(r'[。！？\n]', coupled) if s.strip())
        
        if not raw_sentences:
            return entity_retention
        
        # 计算保留的句子占原相关句子的比例
        relevant_raw = set(s for s in raw_sentences if any(kw in s for kw in keywords))
        if not relevant_raw:
            return entity_retention
        
        retained_sentences = relevant_raw & coupled_sentences
        sentence_retention = len(retained_sentences) / len(relevant_raw)
        
        # 综合实体和句子保留率
        return (entity_retention + sentence_retention) / 2
    
    def _log_metrics(self, metrics: RetrievalMetrics):
        """记录指标到 JSONL 文件"""
        with open(self.metrics_log_path, "a", encoding="utf-8") as f:
            f.write(metrics.to_jsonl() + "\n")


# ============================================================
# A/B 测试与统计显著性检验
# ============================================================

TEST_CASES = [
    {"query": "TU-8 的 L0 安全验证流程", "context": "用户已通过口令验证"},
    {"query": "V0.2.23 版本变更内容", "context": "正在做版本审计"},
    {"query": "记忆宫殿 2.0 架构设计", "context": "讨论脑机接口启发优化"},
    {"query": "电容耦合检索实现", "context": "代码实现阶段"},
    {"query": "外协建议 Qwen3.7-Max", "context": "技术反馈整合"},
]


def run_ab_test(num_runs: int = 5, use_mock: bool = True):
    """
    A/B 测试：对比直接检索 vs 电容耦合检索
    
    Args:
        num_runs: 每个测试用例跑几次（用于统计显著性）
        use_mock: 是否使用模拟数据
    """
    retriever = CapacitiveRetriever(
        max_coupling_strength=0.3,
        feature_extraction_method="llm",
        use_mock_data=use_mock
    )
    
    default_metrics = []
    capacitive_metrics = []
    
    for case in TEST_CASES:
        print(f"\n{'='*60}")
        print(f"测试用例: {case['query']}")
        
        for run in range(num_runs):
            # A 组：直接检索
            result_default = retriever.retrieve(
                query=case["query"],
                current_context=case["context"],
                mode="default"
            )
            default_metrics.append(asdict(result_default["metrics"]))
            
            # B 组：电容耦合
            result_capacitive = retriever.retrieve(
                query=case["query"],
                current_context=case["context"],
                mode="capacitive"
            )
            capacitive_metrics.append(asdict(result_capacitive["metrics"]))
        
        # 打印当前用例的对比
        avg_noise_default = np.mean([m["noise_ratio"] for m in default_metrics[-num_runs:]])
        avg_noise_cap = np.mean([m["noise_ratio"] for m in capacitive_metrics[-num_runs:]])
        avg_retention = np.mean([m["feature_retention"] for m in capacitive_metrics[-num_runs:]])
        
        print(f"  噪声比: {avg_noise_default:.2%} → {avg_noise_cap:.2%}")
        print(f"  特征保留率: {avg_retention:.2%}")
    
    # 统计显著性检验
    print(f"\n{'='*60}")
    print("📊 统计显著性检验结果：")
    analyze_results(default_metrics, capacitive_metrics)
    
    return default_metrics, capacitive_metrics


def analyze_results(default_metrics: list, capacitive_metrics: list):
    """
    对比两组指标，输出统计显著性
    
    Args:
        default_metrics: 直接检索的指标列表
        capacitive_metrics: 电容耦合的指标列表
    """
    metrics_to_compare = ['token_consumed', 'noise_ratio', 'latency_ms', 'feature_retention']
    
    for metric in metrics_to_compare:
        d_vals = [m[metric] for m in default_metrics]
        c_vals = [m[metric] for m in capacitive_metrics]
        
        t_stat, p_value = stats.ttest_ind(d_vals, c_vals)
        
        if metric == 'feature_retention':
            # 特征保留率应该高（电容耦合应该保留关键信息）
            improvement = (np.mean(c_vals) - np.mean(d_vals)) / max(np.mean(d_vals), 0.01) * 100
        else:
            # 其他指标应该低（Token 消耗、噪声比、延迟应该降低）
            improvement = (np.mean(d_vals) - np.mean(c_vals)) / max(np.mean(d_vals), 0.01) * 100
        
        print(f"\n{metric}:")
        print(f"  Default:   {np.mean(d_vals):.2f} ± {np.std(d_vals):.2f}")
        print(f"  Capacitive: {np.mean(c_vals):.2f} ± {np.std(c_vals):.2f}")
        
        if metric == 'feature_retention':
            print(f"  改善: {improvement:+.1f}% (越高越好) | p={p_value:.4f} {'✅ 显著' if p_value < 0.05 else '❌ 不显著'}")
        else:
            print(f"  改善: {improvement:+.1f}% (越低越好) | p={p_value:.4f} {'✅ 显著' if p_value < 0.05 else '❌ 不显著'}")


if __name__ == "__main__":
    print("🧠 TU-8 记忆宫殿 2.0 - 电容耦合检索 A/B 测试")
    print("=" * 60)
    run_ab_test(num_runs=5, use_mock=True)
    print("\n✅ 测试完成！指标已记录到 memory/test_capacitive_metrics.jsonl")
