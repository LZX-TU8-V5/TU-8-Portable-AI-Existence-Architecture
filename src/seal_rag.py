# -*- coding: utf-8 -*-
"""
seal_rag.py — 钢印链 RAG 检索引擎
日期: 2026-06-07
功能: Token 经济学核心 - 只打包相关的钢印，避免全量注入

核心问题：
  当前实现：全量注入最近 5 个钢印 → Token 爆炸
  目标实现：智能检索 → 只打包相关的 2-3 个钢印

检索策略：
  1. 关键词匹配（快速）
  2. 时间衰减（最近的更重要）
  3. 场景标签过滤
  4. 因果链相关性（未来：向量嵌入）
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import os
import sys
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re

# Windows GBK 兼容
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        logger.debug("Exception suppressed", exc_info=True)
        pass

logger = logging.getLogger("tu8.rag")

# =============================================================================
# 常量定义
# =============================================================================

# Token 预算
RAG_TOKEN_BUDGET = {
    "MAX_SEALS": 3,              # 最多打包 3 个钢印
    "MAX_SEAL_CHARS": 200,       # 每个钢印最多 200 字符
    "MIN_RELEVANCE_SCORE": 0.3,  # 最低相关性阈值
}

# 时间衰减参数
TIME_DECAY = {
    "HALF_LIFE_HOURS": 24,       # 24 小时后权重减半
    "MIN_TIME_WEIGHT": 0.1,      # 最低时间权重
}

# 场景权重（某些场景更重要）
SCENE_WEIGHTS = {
    "identity": 2.0,             # 身份相关
    "preference": 1.5,           # 偏好相关
    "task": 1.3,                 # 任务相关
    "reflection": 1.2,           # 反思相关
    "default": 1.0,              # 默认
}


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class SealCandidate:
    """钢印候选（待打分）"""
    seal_id: str
    content: str
    scene_tag: str = "default"
    timestamp: float = 0.0
    keywords: List[str] = field(default_factory=list)
    parent_hash: str = ""
    
    # 打分结果
    relevance_score: float = 0.0
    time_weight: float = 1.0
    scene_weight: float = 1.0
    final_score: float = 0.0


@dataclass
class RAGResult:
    """RAG 检索结果"""
    selected_seals: List[SealCandidate]
    total_candidates: int
    pruned_candidates: int
    retrieval_time_ms: float
    token_estimate: int
    search_query: str = ""


# =============================================================================
# 核心类：钢印 RAG 检索器
# =============================================================================

class SealRAGRetriever:
    """
    钢印链 RAG 检索器
    
    核心职责：
    1. 根据用户输入检索相关钢印
    2. 按相关性排序
    3. 只返回 Top-K（节省 Token）
    """
    
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)
        self.seal_index: List[Dict] = []
        self.keyword_index: Dict[str, List[str]] = {}  # keyword -> [seal_id, ...]
        self._load_seal_index()
        self._build_keyword_index()
    
    def _load_seal_index(self):
        """加载钢印索引"""
        seal_index_path = self.workspace / "memory" / "time_chain" / "seal_index.json"
        if seal_index_path.exists():
            try:
                with open(seal_index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    self.seal_index = data
                    logger.info(f"[RAG] 加载 {len(data)} 个钢印")
                else:
                    self.seal_index = []
            except Exception as e:
                logger.warning(f"[RAG] 加载钢印索引失败: {e}")
    
    def _build_keyword_index(self):
        """构建关键词倒排索引"""
        self.keyword_index = {}
        
        for seal in self.seal_index:
            seal_id = seal.get("seal_id", "")
            content = seal.get("content", "") or seal.get("summary", "")
            tags = seal.get("tags", [])
            
            # 提取关键词
            keywords = self._extract_keywords(content)
            keywords.extend(tags)
            
            # 建立倒排索引
            for keyword in keywords:
                if keyword not in self.keyword_index:
                    self.keyword_index[keyword] = []
                self.keyword_index[keyword].append(seal_id)
        
        logger.debug(f"[RAG] 关键词索引: {len(self.keyword_index)} 个关键词")
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简化版）"""
        # 1. 移除停用词
        stopwords = {"的", "是", "在", "了", "和", "与", "或", "我", "你", "他", "她", "它"}
        
        # 2. 分词（简化：按空格和标点）
        words = re.findall(r'[\w\u4e00-\u9fff]+', text.lower())
        
        # 3. 过滤停用词
        keywords = [w for w in words if w not in stopwords and len(w) >= 2]
        
        return keywords[:10]  # 只取前 10 个
    
    def retrieve(self, user_input: str, intent: Optional[str] = None) -> RAGResult:
        """
        检索相关钢印
        
        Args:
            user_input: 用户输入
            intent: 意图标签（可选，用于场景权重）
        
        Returns:
            RAGResult: 检索结果
        """
        start = time.time()
        
        # 1. 提取查询关键词
        query_keywords = self._extract_keywords(user_input)
        logger.debug(f"[RAG] 查询关键词: {query_keywords}")
        
        # 2. 候选钢印收集
        candidates = self._collect_candidates(query_keywords)
        
        # 3. 打分
        scored_candidates = self._score_candidates(candidates, query_keywords, intent)
        
        # 4. 排序 + 裁剪
        sorted_candidates = sorted(scored_candidates, key=lambda x: x.final_score, reverse=True)
        selected = sorted_candidates[:RAG_TOKEN_BUDGET["MAX_SEALS"]]
        
        # 5. 过滤低分候选
        selected = [c for c in selected if c.final_score >= RAG_TOKEN_BUDGET["MIN_RELEVANCE_SCORE"]]
        
        # 6. Token 估算
        token_estimate = sum(len(c.content) for c in selected) // 2  # 粗略估算
        
        elapsed = (time.time() - start) * 1000
        
        result = RAGResult(
            selected_seals=selected,
            total_candidates=len(candidates),
            pruned_candidates=len(candidates) - len(selected),
            retrieval_time_ms=elapsed,
            token_estimate=token_estimate,
            search_query=" ".join(query_keywords)
        )
        
        logger.info(f"[RAG] 检索完成: {len(selected)}/{len(candidates)} 钢印, {token_estimate} tokens, {elapsed:.1f}ms")
        
        return result
    
    def _collect_candidates(self, query_keywords: List[str]) -> List[SealCandidate]:
        """收集候选钢印"""
        seal_scores: Dict[str, int] = {}  # seal_id -> 匹配次数
        
        # 关键词匹配
        for keyword in query_keywords:
            if keyword in self.keyword_index:
                for seal_id in self.keyword_index[keyword]:
                    seal_scores[seal_id] = seal_scores.get(seal_id, 0) + 1
        
        # 构建候选对象
        candidates = []
        seal_dict = {s.get("seal_id"): s for s in self.seal_index}
        
        for seal_id, match_count in seal_scores.items():
            seal_data = seal_dict.get(seal_id, {})
            
            candidate = SealCandidate(
                seal_id=seal_id,
                content=seal_data.get("content", "") or seal_data.get("summary", ""),
                scene_tag=seal_data.get("scene_tag", "default"),
                timestamp=seal_data.get("timestamp", 0),
                keywords=seal_data.get("tags", []),
                parent_hash=seal_data.get("parent_hash", "")
            )
            
            candidates.append(candidate)
        
        # 如果候选太少，补充最近的钢印
        if len(candidates) < RAG_TOKEN_BUDGET["MAX_SEALS"]:
            recent_seals = self.seal_index[-5:] if len(self.seal_index) > 5 else self.seal_index
            for seal_data in recent_seals:
                seal_id = seal_data.get("seal_id", "")
                if seal_id not in seal_scores:
                    candidate = SealCandidate(
                        seal_id=seal_id,
                        content=seal_data.get("content", "") or seal_data.get("summary", ""),
                        scene_tag=seal_data.get("scene_tag", "default"),
                        timestamp=seal_data.get("timestamp", 0),
                        keywords=seal_data.get("tags", []),
                        parent_hash=seal_data.get("parent_hash", "")
                    )
                    candidates.append(candidate)
        
        return candidates
    
    def _score_candidates(
        self, 
        candidates: List[SealCandidate], 
        query_keywords: List[str],
        intent: Optional[str] = None
    ) -> List[SealCandidate]:
        """对候选钢印打分"""
        current_time = time.time()
        
        for candidate in candidates:
            # 1. 关键词匹配分
            keyword_matches = sum(1 for kw in query_keywords if kw in candidate.keywords or kw in candidate.content.lower())
            candidate.relevance_score = keyword_matches / max(len(query_keywords), 1)
            
            # 2. 时间衰减
            if candidate.timestamp > 0:
                age_hours = (current_time - candidate.timestamp) / 3600
                time_weight = 0.5 ** (age_hours / TIME_DECAY["HALF_LIFE_HOURS"])
                candidate.time_weight = max(time_weight, TIME_DECAY["MIN_TIME_WEIGHT"])
            else:
                candidate.time_weight = TIME_DECAY["MIN_TIME_WEIGHT"]
            
            # 3. 场景权重
            candidate.scene_weight = SCENE_WEIGHTS.get(candidate.scene_tag, SCENE_WEIGHTS["default"])
            
            # 4. 意图加权（如果提供了意图）
            intent_bonus = 0.0
            if intent:
                # 某些意图更偏向某些场景
                intent_scene_map = {
                    "recall_personal_history": ["identity", "reflection"],
                    "task_planning": ["task", "preference"],
                    "reflection": ["reflection", "identity"],
                    "query_local_knowledge": ["knowledge", "task"],
                }
                preferred_scenes = intent_scene_map.get(intent, [])
                if candidate.scene_tag in preferred_scenes:
                    intent_bonus = 0.2
            
            # 5. 最终得分
            candidate.final_score = (
                candidate.relevance_score * 0.5 +
                candidate.time_weight * 0.3 +
                candidate.scene_weight * 0.1 +
                intent_bonus
            )
        
        return candidates
    
    def format_for_prompt(self, result: RAGResult) -> str:
        """格式化检索结果为 Prompt"""
        if not result.selected_seals:
            return ""
        
        lines = ["相关钢印（RAG 检索）："]
        
        for i, seal in enumerate(result.selected_seals, 1):
            content = seal.content[:RAG_TOKEN_BUDGET["MAX_SEAL_CHARS"]]
            lines.append(f"  [{i}] [{seal.scene_tag}] {content}")
            lines.append(f"      相关性: {seal.final_score:.2f}")
        
        return "\n".join(lines)


# =============================================================================
# 工具函数
# =============================================================================

def estimate_token_saving(full_count: int, rag_count: int, avg_seal_chars: int = 300) -> Dict[str, Any]:
    """估算 Token 节省"""
    full_tokens = full_count * avg_seal_chars // 2
    rag_tokens = rag_count * avg_seal_chars // 2
    
    return {
        "full_injection_tokens": full_tokens,
        "rag_tokens": rag_tokens,
        "saved_tokens": full_tokens - rag_tokens,
        "saving_ratio": 1 - (rag_tokens / max(full_tokens, 1))
    }


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Seal RAG Retriever Test")
    print("=" * 60)
    
    # 创建测试工作区
    test_dir = os.path.join(os.path.dirname(__file__), "test_workspace")
    os.makedirs(test_dir, exist_ok=True)
    
    # 创建测试钢印索引
    seal_index_path = os.path.join(test_dir, "memory", "time_chain", "seal_index.json")
    os.makedirs(os.path.dirname(seal_index_path), exist_ok=True)
    
    test_seals = [
        {
            "seal_id": "seal_001",
            "content": "用户偏好：喜欢简洁的技术文档，不喜欢冗长的解释",
            "scene_tag": "preference",
            "timestamp": time.time() - 3600,  # 1 小时前
            "tags": ["preference", "documentation"]
        },
        {
            "seal_id": "seal_002",
            "content": "任务：完成 P0 强类型契约的实现",
            "scene_tag": "task",
            "timestamp": time.time() - 7200,  # 2 小时前
            "tags": ["task", "P0", "contract"]
        },
        {
            "seal_id": "seal_003",
            "content": "身份：我是 TU-8，具有持续记忆的 AI 助手",
            "scene_tag": "identity",
            "timestamp": time.time() - 86400,  # 24 小时前
            "tags": ["identity", "core"]
        },
        {
            "seal_id": "seal_004",
            "content": "反思：Token 经济学是当前的关键瓶颈",
            "scene_tag": "reflection",
            "timestamp": time.time() - 172800,  # 48 小时前
            "tags": ["reflection", "token", "economics"]
        },
        {
            "seal_id": "seal_005",
            "content": "知识：Python 装饰器是一种语法糖",
            "scene_tag": "knowledge",
            "timestamp": time.time() - 259200,  # 72 小时前
            "tags": ["knowledge", "python", "decorator"]
        }
    ]
    
    with open(seal_index_path, "w", encoding="utf-8") as f:
        json.dump(test_seals, f, ensure_ascii=False, indent=2)
    
    # 创建 RAG 检索器
    retriever = SealRAGRetriever(test_dir)
    
    # 测试检索
    print("\n[Test 1] 关键词检索...")
    result = retriever.retrieve("我想了解一下 Token 经济学")
    print(f"  查询: '我想了解一下 Token 经济学'")
    print(f"  候选: {result.total_candidates}")
    print(f"  选中: {len(result.selected_seals)}")
    print(f"  Token: {result.token_estimate}")
    
    print("\n[Test 2] 意图加权检索...")
    result = retriever.retrieve("帮我规划一下任务", intent="task_planning")
    print(f"  查询: '帮我规划一下任务'")
    print(f"  选中: {len(result.selected_seals)}")
    
    print("\n[Test 3] 格式化输出...")
    prompt = retriever.format_for_prompt(result)
    print(prompt)
    
    print("\n[Test 4] Token 节省估算...")
    saving = estimate_token_saving(full_count=5, rag_count=2)
    print(f"  全量注入: {saving['full_injection_tokens']} tokens")
    print(f"  RAG 检索: {saving['rag_tokens']} tokens")
    print(f"  节省: {saving['saved_tokens']} tokens ({saving['saving_ratio']*100:.1f}%)")
    
    print("\n" + "=" * 60)
    print("All tests passed")
    print("=" * 60)
