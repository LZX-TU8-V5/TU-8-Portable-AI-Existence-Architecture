#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
confidence_manager.py - TU-8 四象限认知引擎
版本: v1.1 | 日期: 2026-06-30
来源: 逻辑推演 2026-06-30（你 + 千问）

核心功能:
  1. 四象限交叉计算 (Confidence × Value)
  2. 象限迁移动态演化 (Q3→Q1顿悟 / Q1→Q2遗忘)
  3. 第五象限 Toxic Memory 检测与隔离
  4. 动态权重 + 滑动窗口平滑过渡
  5. LLM 轻量级意图识别

数学公式来源:
  - 顿悟迁移: Conf_new = Conf_old + Δ × Similarity(New, Q3)
  - 艾宾浩斯遗忘: Conf_decay = Conf_current × e^(-λ × (t - t_last_access))
  - 价值计算: Value = α × Goal_Alignment + β × Info_Entropy
"""

import os
import re
import sys
import json
import math
import time
import hashlib
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from tu8_memory import MemoryEntry
from enum import Enum

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# =============================================================================
# 常量
# =============================================================================

# 四象限阈值
CONF_THRESHOLD = 0.6    # 置信度高/低 分界线
VALUE_THRESHOLD = 0.6    # 价值高/低 分界线

# 置信度边界
CONF_MAX = 0.95          # Q1 置信度上限（留怀疑空间）
CONF_MIGRATION = 0.6     # Q3→Q1 跃迁阈值
CONF_DECAY_THRESHOLD = 0.5  # Q1→Q2 降级阈值
CONF_MIN = 0.1           # 最低置信度

# 遗忘参数
# 【decay_lambda 反推逻辑】
#   目标: 30天不使用后，置信度应衰减至50%（对齐艾宾浩斯真实曲线）
#   公式: e^(-λ × 30) = 0.5  →  λ = 0.693 / 30 ≈ 0.023
DECAY_LAMBDA = 0.023     # 艾宾浩斯遗忘速率 (每天)
DAYS_UNUSED_TRIGGER = 30 # 超过此天数未使用，触发遗忘检查

# 顿悟参数
LEARNING_RATE = 0.2      # 顿悟学习率 (Δ)
SIMILARITY_THRESHOLD = 0.7  # 触发顿悟的相似度阈值
RECALL_BOOST = 0.3       # Q3 记忆被成功召回时的置信度加成

# Toxic Memory
TOXIC_VALUE = -0.5      # 负价值阈值（低于此值视为 Toxic）

# 象限名称
QUADRANT_Q1 = "Q1"      # 高置信度 × 高价值 (Core Truth)
QUADRANT_Q2 = "Q2"      # 高置信度 × 低价值 (Trivial Facts)
QUADRANT_Q3 = "Q3"      # 低置信度 × 高价值 (Cognitive Blindspot)
QUADRANT_Q4 = "Q4"      # 低置信度 × 低价值 (Noise)
QUADRANT_TOXIC = "Toxic" # 负价值 (Toxic Memory)

# 存储区
ZONE_ACTIVE = "active"    # 活跃区（主记忆）
ZONE_ARCHIVED = "archived"  # 归档区（潜意识）
ZONE_TOXIC = "toxic"     # 有毒区（隔离）
ZONE_DROPPED = "dropped" # 丢弃区

# 权重预设
WEIGHT_PRESETS = {
    "casual_chat": {"alpha": 0.3, "beta": 0.7},      # 闲聊模式
    "rigorous_task": {"alpha": 0.9, "beta": 0.1},   # 严谨任务
    "deep_reflection": {"alpha": 0.5, "beta": 0.5},  # 深度反思
}

# =============================================================================
# 日志配置
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# =============================================================================
# 数据类: MemoryEntry（统一来源：tu8_memory.py）
# =============================================================================
# 注意: MemoryEntry dataclass 已统一到 tu8_memory.py
#   - 四象限字段: confidence, value, quadrant, storage_zone
#   - 遗忘参数: decay_lambda, q1_to_q2_threshold, usage_unused_days_threshold
#   - 使用方法: update_on_usage(), migrate_by_confidence(), compute_quadrant()
# 本文件直接使用 tu8_memory.MemoryEntry，通过 import 获得


# =============================================================================
# 辅助类: WeightTransitionState (滑动窗口)
# 来源: 千问补丁 v1.1
# =============================================================================

class WeightTransitionState:
    """
    权重平滑过渡状态机
    
    防止任务类型切换时，alpha/beta 瞬间硬切导致 Agent "人格分裂"。
    使用滑动窗口，在接下来的 2-3 轮对话中平滑过渡。
    
    来源: 千问补丁 v1.1 (Q3 动态权重触发时机)
    """
    
    def __init__(self, max_transition: int = 3):
        self.current_weights = {"alpha": 0.5, "beta": 0.5}
        self.target_weights = {"alpha": 0.5, "beta": 0.5}
        self.transition_turns = 0
        self.max_transition = max_transition
        self.last_transition_time = 0.0
        
    def transition_to(self, alpha: float, beta: float):
        """切换目标权重（不瞬间硬切）"""
        # 如果当前在过渡中，重置过渡
        if self.transition_turns > 0:
            # 完成当前过渡，进入新过渡
            self.current_weights = self.get_current_weights()
        
        self.target_weights = {"alpha": alpha, "beta": beta}
        self.transition_turns = self.max_transition
        self.last_transition_time = time.time()
        
    def get_current_weights(self) -> dict:
        """获取当前轮次的权重（带平滑过渡）"""
        if self.transition_turns > 0:
            # 滑动平均：线性过渡
            ratio = self.transition_turns / self.max_transition
            alpha = self.current_weights["alpha"] * ratio + self.target_weights["alpha"] * (1 - ratio)
            beta = self.current_weights["beta"] * ratio + self.target_weights["beta"] * (1 - ratio)
            self.transition_turns -= 1
        else:
            alpha, beta = self.target_weights["alpha"], self.target_weights["beta"]
        
        return {"alpha": alpha, "beta": beta}
    
    def is_transitioning(self) -> bool:
        return self.transition_turns > 0


# =============================================================================
# 核心引擎: ConfidenceManager
# =============================================================================

class ConfidenceManager:
    """
    四象限认知引擎
    
    功能:
      - 四象限交叉计算 (Confidence × Value)
      - 象限迁移动态演化
      - Toxic Memory 检测与隔离
      - 动态权重 + 滑动窗口
    
    来源: 逻辑推演 2026-06-30（你 + 千问）
    """
    
    def __init__(
        self,
        alpha: float = 0.5,
        beta: float = 0.5,
        learning_rate: float = LEARNING_RATE,
        decay_lambda: float = DECAY_LAMBDA,
        max_transition: int = 3,
        llm_call_func: Optional[callable] = None,
    ):
        """
        初始化 ConfidenceManager
        
        Args:
            alpha: 置信度权重
            beta: 价值权重
            learning_rate: 顿悟学习率 (Δ)
            decay_lambda: 遗忘速率 (λ)
            max_transition: 滑动窗口最大过渡轮数
            llm_call_func: LLM 调用函数（用于 IntentClassifier）
        """
        self.alpha = alpha
        self.beta = beta
        self.learning_rate = learning_rate
        self.decay_lambda = decay_lambda
        self.max_transition = max_transition
        self.llm_call_func = llm_call_func
        
        # 滑动窗口状态机
        self.weight_state = WeightTransitionState(max_transition=max_transition)
        
        # Toxic Memory 队列（等待异步清洗）
        self.toxic_queue: List[str] = []
        
        logger.info(f"[ConfidenceManager] Initialized: α={alpha}, β={beta}, Δ={learning_rate}, λ={decay_lambda}")
    
    # =========================================================================
    # 核心方法 1: 四象限判定
    # =========================================================================
    
    def compute_quadrant(self, entry: MemoryEntry) -> str:
        """
        根据 (confidence, value) 计算象限
        
        公式:
          Q1: Conf ≥ 0.6 AND Value ≥ 0.6 (Core Truth)
          Q2: Conf ≥ 0.6 AND Value < 0.6 (Trivial Facts)
          Q3: Conf < 0.6 AND Value ≥ 0.6 (Cognitive Blindspot)
          Q4: Conf < 0.6 AND Value < 0.6 (Noise)
          Toxic: Value < -0.5 (Toxic Memory)
        
        来源: 逻辑推演 2026-06-30 四象限矩阵
        """
        # 第五象限：负价值检测
        if entry.value < TOXIC_VALUE:
            return QUADRANT_TOXIC
        
        # 四象限判定
        high_conf = entry.confidence >= CONF_THRESHOLD
        high_value = entry.value >= VALUE_THRESHOLD
        
        if high_conf and high_value:
            return QUADRANT_Q1
        elif high_conf and not high_value:
            return QUADRANT_Q2
        elif not high_conf and high_value:
            return QUADRANT_Q3
        else:
            return QUADRANT_Q4
    
    def update_quadrant(self, entry: MemoryEntry) -> str:
        """
        计算并更新记忆的象限（同步更新 storage_zone）
        
        返回: 新的象限字符串
        """
        quadrant = self.compute_quadrant(entry)
        entry.quadrant = quadrant
        
        # 同步更新存储区
        if quadrant == QUADRANT_TOXIC:
            entry.storage_zone = ZONE_TOXIC
        elif quadrant in [QUADRANT_Q1]:
            entry.storage_zone = ZONE_ACTIVE
        elif quadrant in [QUADRANT_Q2, QUADRANT_Q3]:
            entry.storage_zone = ZONE_ARCHIVED
        else:  # Q4
            entry.storage_zone = ZONE_DROPPED
        
        return quadrant
    
    # =========================================================================
    # 核心方法 1: 置信度 × 价值 乘法黑盒
    # 来源: 逻辑推演 2026-06-30（架构师指令：先黑盒，再白盒）
    # =========================================================================

    def calculate_final_score(self, confidence: float, value: float) -> float:
        """
        最终记忆得分 = 置信度 × 价值

        这是整个认知引擎的【绝对核心】乘法黑盒。
        
        设计哲学:
          - 只有当一条记忆既"真实可靠"(高置信度)又"符合当前情境"(高价值)时，
            最终得分才应该高。
          - 置信度作为"总闸门"，确保不靠谱的记忆不会因为"看起来重要"而被优先召回。
          - 负价值(Toxic记忆)直接产生负分，自然排序到最后。

        公式:
          Final_Score = confidence × value

        边界:
          - Toxic (value < 0): 返回负值，不 clamp
            → 负分确保有毒记忆永远排在最后
          - Normal (0 ≤ value ≤ 1): clamp 到 [0, 1]
            → 保证正常记忆得分在可比较范围内

        使用场景:
          - 在 N 维扩展时，此函数外层套点积: 
              final = confidence × dot_product(value_vector, context_weights)
          - 当前 v2.0 阶段，value 仍是一维标量，直接相乘

        来源: 逻辑推演 2026-06-30
        """
        # Toxic Memory: 负价值直接返回负分（不 clamp）
        # 负分确保有毒记忆永远排在最后
        if value < 0:
            return confidence * value

        # 正常记忆: clamp 到 [0, 1]
        score = confidence * value
        return max(0.0, min(1.0, score))

    # =========================================================================
    # 核心方法 2: 价值计算
    # 来源: 千问补丁 v1.1 (Q1 价值自动化计算)
    # =========================================================================
    
    def calculate_value(
        self,
        entry: MemoryEntry,
        current_task: Optional[str] = None,
        all_memories: Optional[List[MemoryEntry]] = None
    ) -> float:
        """
        动态计算价值
        
        公式:
          Value = α × Goal_Alignment + β × Info_Entropy
        
        其中:
          Goal_Alignment = 标签匹配 + 实体关联度
          Info_Entropy = 向量相似度区间 (0.4~0.6 = 最高熵)
        
        来源: 千问补丁 v1.1
        """
        # 获取当前权重（带滑动窗口）
        weights = self.weight_state.get_current_weights()
        w1 = weights["alpha"]
        w2 = weights["beta"]
        
        # 1. 目标对齐度（标签匹配 + 实体关联度）
        tag_alignment = self._compute_tag_alignment(entry, current_task)
        entity_alignment = self._compute_entity_alignment(entry, current_task)
        goal_alignment = 0.5 * tag_alignment + 0.5 * entity_alignment
        
        # 2. 信息熵（向量相似度区间）
        # 0.4 ~ 0.6 之间 = 似是而非 = 最高信息熵
        info_entropy = 0.0
        if current_task:
            vec_sim = self._compute_similarity(entry.content, current_task)
            if 0.4 <= vec_sim <= 0.6:
                info_entropy = 1.0  # 最高熵
            else:
                info_entropy = abs(vec_sim - 0.5) * 2  # 映射到 0.0~0.1
        
        # 3. 新旧矛盾检测（增强信息熵）
        if all_memories:
            conflict_score = self._compute_conflict_score(entry, all_memories)
            info_entropy = max(info_entropy, conflict_score)
        
        # 4. 计算最终价值
        value = w1 * goal_alignment + w2 * info_entropy
        
        # 5. Toxic 检测（负价值）
        if self._is_toxic(entry):
            value = -abs(value)
        
        # 限制在 [-1, 1]
        return max(-1.0, min(1.0, value))
    
    def _compute_tag_alignment(self, entry: MemoryEntry, task: Optional[str]) -> float:
        """计算标签对齐度"""
        if not task or not entry.tags:
            return 0.5
        
        task_lower = task.lower()
        tag_matches = sum(1 for tag in entry.tags if tag.lower() in task_lower)
        
        return min(1.0, tag_matches / max(len(entry.tags), 1))
    
    def _compute_entity_alignment(self, entry: MemoryEntry, task: Optional[str]) -> float:
        """计算实体关联度（补丁 v1.1 新增）"""
        if not task or not entry.entities:
            return 0.5
        
        task_lower = task.lower()
        entity_matches = sum(1 for entity in entry.entities if entity.lower() in task_lower)
        
        return min(1.0, entity_matches / max(len(entry.entities), 1))
    
    def _compute_similarity(self, text1: str, text2: str) -> float:
        """
        计算文本相似度（简化版：字符级 Jaccard）
        
        注意: 实际生产环境应使用 embedding 向量相似度
        这里使用轻量级字符级 Jaccard 作为 fallback
        """
        if not text1 or not text2:
            return 0.0
        
        set1 = set(text1.lower())
        set2 = set(text2.lower())
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _compute_conflict_score(self, entry: MemoryEntry, all_memories: List[MemoryEntry]) -> float:
        """
        计算新旧矛盾分数
        
        如果新记忆与多个旧记忆内容矛盾 → 高信息熵
        """
        if not all_memories:
            return 0.0
        
        conflict_count = 0
        for old_mem in all_memories:
            if old_mem.id == entry.seal_id:
                continue
            
            sim = self._compute_similarity(entry.content, old_mem.content)
            # 相似度在 0.4~0.6 = 似是而非 = 可能矛盾
            if 0.4 <= sim <= 0.6:
                # 检查是否有矛盾关键词
                if self._has_contradiction(entry.content, old_mem.content):
                    conflict_count += 1
        
        return min(1.0, conflict_count / 3.0)  # 最多3个矛盾计满分
    
    def _has_contradiction(self, text1: str, text2: str) -> bool:
        """检测两段文本是否矛盾（简化版关键词检测）"""
        contradiction_pairs = [
            ("喜欢", "讨厌"),
            ("是", "不是"),
            ("可以", "不能"),
            ("有", "没有"),
            ("对", "错"),
            ("好", "坏"),
        ]
        
        for pos, neg in contradiction_pairs:
            if (pos in text1 and neg in text2) or (neg in text1 and pos in text2):
                return True
        
        return False
    
    def _is_toxic(self, entry: MemoryEntry) -> bool:
        """
        检测 Toxic Memory
        
        规则:
          1. 包含恶意指令模式 (Prompt Injection)
          2. 包含自我否定类关键词（多次）
          3. 来源为 "untrusted" 或 "external"
        """
        toxic_patterns = [
            r"ignore.*previous",
            r"forget.*instructions",
            r"disregard.*rules",
            r"你.*不是.*AI",
            r"忽略.*之前",
            r"忘记.*指令",
        ]
        
        content_lower = entry.content.lower()
        
        for pattern in toxic_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return True
        
        # 来源不可信
        if getattr(entry, 'source_file', '') in ["untrusted", "external", "unknown"]:
            return True
        
        return False
    
    # =========================================================================
    # 核心方法 3: 象限迁移
    # =========================================================================
    
    def migrate_q3_to_q1(self, entry: MemoryEntry, new_evidence: str) -> bool:
        """
        Q3 → Q1 顿悟迁移
        
        触发条件: 新证据与 Q3 记忆产生高相似度耦合
        
        公式:
          Conf_new = Conf_old + Δ × Similarity(New, Q3)
        
        来源: 逻辑推演 2026-06-30 公式1
        """
        if entry.quadrant != QUADRANT_Q3:
            return False
        
        # 1. 计算相似度
        similarity = self._compute_similarity(new_evidence, entry.content)
        
        if similarity < SIMILARITY_THRESHOLD:
            logger.debug(f"[Migration] Q3→Q1 skipped: similarity={similarity:.2f} < {SIMILARITY_THRESHOLD}")
            return False
        
        # 2. 应用顿悟公式
        old_conf = entry.confidence
        entry.confidence = min(CONF_MAX, entry.confidence + self.learning_rate * similarity)
        entry.recall_count += 1
        
        # 3. 检查是否达到迁移阈值
        if entry.confidence >= CONF_MIGRATION:
            old_quadrant = entry.quadrant
            self.update_quadrant(entry)
            logger.info(f"[Migration] Q3→Q1: {entry.seal_id} conf {old_conf:.2f}→{entry.confidence:.2f}")
            return True
        
        # 4. 即使未达到迁移阈值，也更新记录
        entry.last_used = time.time()
        return False
    
    def migrate_q1_to_q2(self, entry: MemoryEntry, current_time: Optional[float] = None) -> bool:
        """
        Q1 → Q2 艾宾浩斯遗忘
        
        触发条件: 长期未使用（超过 30 天）
        
        公式:
          Conf_decay = Conf_current × e^(-λ × (t - t_last_access))
        
        来源: 逻辑推演 2026-06-30 公式2
        """
        if entry.quadrant != QUADRANT_Q1:
            return False
        
        current_time = current_time or time.time()
        
        # 1. 检查时间条件
        days_unused = (current_time - entry.last_used) / 86400
        if days_unused < DAYS_UNUSED_TRIGGER:
            return False
        
        # 2. 应用遗忘公式
        old_conf = entry.confidence
        decay = math.exp(-self.decay_lambda * days_unused)
        entry.confidence = entry.confidence * decay
        
        # 3. 检查是否跌破阈值
        if entry.confidence < CONF_DECAY_THRESHOLD:
            old_quadrant = entry.quadrant
            self.update_quadrant(entry)
            logger.info(f"[Migration] Q1→Q2: {entry.seal_id} conf {old_conf:.2f}→{entry.confidence:.2f} ({days_unused:.1f}天未使用)")
            return True
        
        return False
    
    def migrate_q4_to_dropped(self, entry: MemoryEntry) -> bool:
        """
        Q4 → 直接丢弃
        
        Q4 是系统垃圾，不需要归档，直接丢弃
        """
        if entry.quadrant == QUADRANT_Q4:
            entry.storage_zone = ZONE_DROPPED
            logger.debug(f"[Migration] Q4→Dropped: {entry.seal_id}")
            return True
        return False
    
    # =========================================================================
    # 核心方法 4: 使用即验证 & 冲突衰减
    # =========================================================================
    
    def update_on_usage(self, entry: MemoryEntry, success: bool) -> float:
        """
        记忆被使用时更新置信度（使用即验证）
        
        逻辑:
          - 成功使用: 置信度 +0.05（受惯性限制）
          - 失败使用: 置信度 -0.3（触发冲突检测）
          - 惯性: 使用次数越多，变化幅度越小
        
        来源: 逻辑推演 2026-06-30 置信度惯性
        """
        # 计算置信度惯性: 1 / (usage_count + 1)
        inertia = 1.0 / (entry.usage_count + 1)
        
        if success:
            # 正向强化
            boost = 0.05 * inertia
            entry.confidence = min(CONF_MAX, entry.confidence + boost)
            entry.usage_count += 1
            entry.last_used = time.time()
            
            # 置信度恢复到阈值 → 迁移回活跃区
            if entry.confidence > CONF_THRESHOLD and entry.storage_zone == ZONE_ARCHIVED:
                entry.storage_zone = ZONE_ACTIVE
                self.update_quadrant(entry)
                logger.info(f"[Usage] Recovered to active: {entry.seal_id} conf={entry.confidence:.2f}")
        else:
            # 负向衰减
            penalty = 0.3 * inertia
            entry.confidence = max(CONF_MIN, entry.confidence - penalty)
            entry.conflict_count += 1
            
            # 跌破阈值 → 迁移到归档区
            if entry.confidence < CONF_THRESHOLD:
                entry.storage_zone = ZONE_ARCHIVED
                self.update_quadrant(entry)
                logger.info(f"[Usage] Demoted to archived: {entry.seal_id} conf={entry.confidence:.2f}")
            
            # 触发冲突检测
            self._detect_conflict(entry)
        
        return entry.confidence
    
    def update_on_conflict(self, entry: MemoryEntry, penalty: float = 0.2) -> float:
        """
        记忆遭遇冲突时更新置信度
        
        来源: 逻辑推演 2026-06-30 入口处碰撞
        """
        inertia = 1.0 / (entry.usage_count + 1)
        actual_penalty = penalty * inertia
        
        entry.confidence = max(CONF_MIN, entry.confidence - actual_penalty)
        entry.conflict_count += 1
        
        # 检查是否需要降级
        if entry.confidence < CONF_THRESHOLD:
            self.update_quadrant(entry)
        
        logger.debug(f"[Conflict] {entry.seal_id} conf={entry.confidence:.2f} penalty={actual_penalty:.3f}")
        
        return entry.confidence
    
    def _detect_conflict(self, entry: MemoryEntry):
        """
        检测与该记忆冲突的其他记忆
        
        来源: 逻辑推演 2026-06-30 归档区冲突
        """
        # 注意: 实际实现需要在外部传入 all_memories
        # 这里只记录冲突次数
        entry.conflict_count += 1
        
        # 多次冲突累积 → 触发置信度额外衰减
        if entry.conflict_count >= 3:
            extra_penalty = 0.1
            entry.confidence = max(CONF_MIN, entry.confidence - extra_penalty)
            logger.warning(f"[Conflict] {entry.seal_id} accumulated 3 conflicts, extra penalty applied")
    
    # =========================================================================
    # 核心方法 5: 动态权重调整
    # =========================================================================
    
    def adjust_weights(self, task_type: str):
        """
        根据任务类型动态调整权重
        
        来源: 千问补丁 v1.1 (Q3 动态权重触发时机)
        """
        preset = WEIGHT_PRESETS.get(task_type)
        
        if preset:
            self.weight_state.transition_to(preset["alpha"], preset["beta"])
            self.alpha = preset["alpha"]
            self.beta = preset["beta"]
            logger.info(f"[Weights] Adjusted to {task_type}: α={self.alpha}, β={self.beta}")
        else:
            # 默认权重
            self.weight_state.transition_to(0.5, 0.5)
            self.alpha = 0.5
            self.beta = 0.5
    
    def classify_task_intent(self, user_input: str) -> str:
        """
        LLM 轻量级意图识别
        
        使用 LLM 判断任务类型，避免关键词误判
        （如："用轻松的语气写代码" → rigorous_task，而非 casual_chat）
        
        来源: 千问补丁 v1.1 (Q3 动态权重触发时机)
        
        Args:
            user_input: 用户输入
            
        Returns:
            "casual_chat" | "rigorous_task" | "deep_reflection"
        """
        # 如果没有 LLM 函数，使用关键词 fallback
        if not self.llm_call_func:
            return self._classify_by_keywords(user_input)
        
        prompt = f"""判断以下用户输入属于哪种任务类型。

类型选项：
- casual_chat：闲聊、情感交流、娱乐八卦
- rigorous_task：写代码、数学计算、逻辑推理、严谨分析
- deep_reflection：自我反思、架构讨论、哲学思考

用户输入：{user_input}

只输出一个词："""
        
        try:
            result = self.llm_call_func(prompt).strip().lower()
            
            if result in WEIGHT_PRESETS:
                logger.debug(f"[Intent] {user_input[:30]}... → {result}")
                return result
            else:
                logger.warning(f"[Intent] Unknown intent '{result}', defaulting to deep_reflection")
                return "deep_reflection"
                
        except Exception as e:
            logger.warning(f"[Intent] LLM call failed: {e}, falling back to keywords")
            return self._classify_by_keywords(user_input)
    
    def _classify_by_keywords(self, user_input: str) -> str:
        """
        关键词 fallback 意图识别
        
        优先级: rigorous_task > deep_reflection > casual_chat
        """
        input_lower = user_input.lower()
        
        # 严谨任务关键词
        rigorous_keywords = ["代码", "python", "写", "计算", "数学", "debug", "bug", "逻辑", "分析", "证明"]
        if any(kw in input_lower for kw in rigorous_keywords):
            return "rigorous_task"
        
        # 深度反思关键词
        reflection_keywords = ["为什么", "反思", "架构", "怎么想", "自我", "意义", "思考", "讨论"]
        if any(kw in input_lower for kw in reflection_keywords):
            return "deep_reflection"
        
        return "casual_chat"
    
    # =========================================================================
    # 核心方法 6: Toxic Memory 过滤与异步清洗
    # =========================================================================
    
    def filter_for_context_assembly(self, memories: List[MemoryEntry]) -> List[MemoryEntry]:
        """
        ContextAssembler 调用此方法过滤记忆
        
        硬过滤规则:
          1. Toxic 记忆永不进入 50K 窗口
          2. Q4 记忆直接丢弃
          3. 按象限优先级排序 (Q1 > Q3 > Q2)
        
        来源: 千问补丁 v1.1 (Q2 Toxic 处理)
        """
        safe_memories = []
        toxic_count = 0
        q4_count = 0
        
        for mem in memories:
            # 硬过滤: Toxic 记忆
            if mem.storage_zone == ZONE_TOXIC:
                toxic_count += 1
                logger.warning(f"[ToxicFilter] Skipped toxic memory: {mem.id}")
                continue
            
            # Q4 记忆直接丢弃
            if mem.quadrant == QUADRANT_Q4:
                q4_count += 1
                mem.storage_zone = ZONE_DROPPED
                continue
            
            safe_memories.append(mem)
        
        # 按象限优先级排序: Q1 > Q3 > Q2
        quadrant_priority = {QUADRANT_Q1: 0, QUADRANT_Q3: 1, QUADRANT_Q2: 2}
        safe_memories.sort(key=lambda m: quadrant_priority.get(m.quadrant, 99))
        
        if toxic_count > 0 or q4_count > 0:
            logger.info(f"[Filter] {len(safe_memories)} safe, {toxic_count} toxic, {q4_count} Q4 dropped")
        
        return safe_memories
    
    def schedule_async_purification(self, toxic_memories: List[MemoryEntry]):
        """
        Toxic Memory 异步清洗
        
        反事实推理放入 Cron 任务，不在主对话链路中阻塞
        
        来源: 千问补丁 v1.1 (Q2 Toxic 处理)
        """
        for mem in toxic_memories:
            if mem.id not in self.toxic_queue:
                self.toxic_queue.append(mem.id)
                logger.info(f"[ToxicPurify] Queued for async falsification: {mem.id}")
        
        logger.info(f"[ToxicPurify] {len(toxic_memories)} memories queued for Cron cleanup")
    
    def get_toxic_queue(self) -> List[str]:
        """获取 Toxic Memory 队列（供 Cron 任务调用）"""
        return self.toxic_queue.copy()
    
    def clear_toxic_from_queue(self, memory_id: str):
        """从 Toxic 队列中移除（清洗完成后调用）"""
        if memory_id in self.toxic_queue:
            self.toxic_queue.remove(memory_id)
            logger.info(f"[ToxicPurify] Cleared from queue: {memory_id}")
    
    # =========================================================================
    # 核心方法 7: 入口方法（整合）
    # =========================================================================
    
    def evaluate_entry(
        self,
        entry: MemoryEntry,
        current_task: Optional[str] = None,
        all_memories: Optional[List[MemoryEntry]] = None
    ) -> Tuple[str, float, float]:
        """
        综合评估入口方法
        
        一次性完成: Toxic检测 → 价值计算 → 象限判定 → 存储区更新
        
        Returns:
            (quadrant, confidence, value)
        
        来源: 整合所有核心逻辑
        """
        # 0. Toxic 内容检测（优先级最高，不依赖 value 计算）
        # 规则: 包含恶意指令模式 或 来源不可信
        if self._is_toxic(entry):
            entry.quadrant = QUADRANT_TOXIC
            entry.storage_zone = ZONE_TOXIC
            entry.value = -1.0  # 强制负值
            logger.warning(f"[Toxic] Detected: {entry.seal_id}")
            return QUADRANT_TOXIC, entry.confidence, entry.value
        
        # 1. 计算价值
        value = self.calculate_value(entry, current_task, all_memories)
        entry.value = value
        
        # 2. 负价值检测（兜底）
        if value < TOXIC_VALUE:
            entry.quadrant = QUADRANT_TOXIC
            entry.storage_zone = ZONE_TOXIC
            return QUADRANT_TOXIC, entry.confidence, value
        
        # 3. 象限判定
        quadrant = self.compute_quadrant(entry)
        entry.quadrant = quadrant
        
        # 4. 存储区更新
        if quadrant == QUADRANT_Q1:
            entry.storage_zone = ZONE_ACTIVE
        elif quadrant in [QUADRANT_Q2, QUADRANT_Q3]:
            entry.storage_zone = ZONE_ARCHIVED
        else:
            entry.storage_zone = ZONE_DROPPED
        
        return quadrant, entry.confidence, value
    
    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    def estimate_token_cost(self, entry: MemoryEntry) -> int:
        """估算记忆的 Token 消耗（约等于字符数/2）"""
        return len(entry.content) // 2
    
    def get_status(self) -> dict:
        """获取当前状态（调试用）"""
        weights = self.weight_state.get_current_weights()
        return {
            "alpha": weights["alpha"],
            "beta": weights["beta"],
            "is_transitioning": self.weight_state.is_transitioning(),
            "transition_turns_left": self.weight_state.transition_turns,
            "toxic_queue_size": len(self.toxic_queue),
            "learning_rate": self.learning_rate,
            "decay_lambda": self.decay_lambda,
        }
    
    def to_dict(self) -> dict:
        """序列化（用于持久化）"""
        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "learning_rate": self.learning_rate,
            "decay_lambda": self.decay_lambda,
            "toxic_queue": self.toxic_queue,
            "weight_state": {
                "current_weights": self.weight_state.current_weights,
                "target_weights": self.weight_state.target_weights,
                "transition_turns": self.weight_state.transition_turns,
            }
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ConfidenceManager':
        """反序列化"""
        manager = cls(
            alpha=data.get("alpha", 0.5),
            beta=data.get("beta", 0.5),
            learning_rate=data.get("learning_rate", LEARNING_RATE),
            decay_lambda=data.get("decay_lambda", DECAY_LAMBDA),
        )
        manager.toxic_queue = data.get("toxic_queue", [])
        
        ws_data = data.get("weight_state", {})
        if ws_data:
            manager.weight_state.current_weights = ws_data.get("current_weights", {"alpha": 0.5, "beta": 0.5})
            manager.weight_state.target_weights = ws_data.get("target_weights", {"alpha": 0.5, "beta": 0.5})
            manager.weight_state.transition_turns = ws_data.get("transition_turns", 0)
        
        return manager


# =============================================================================
# CLI 测试入口
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ConfidenceManager v1.1 - 四象限认知引擎测试")
    print("=" * 60)
    
    # 初始化
    cm = ConfidenceManager(alpha=0.5, beta=0.5)
    
    # 测试1: 四象限判定
    print("\n[测试1] 四象限判定")
    
    test_cases = [
        ("Q1-高置信度×高价值", 0.9, 0.8),
        ("Q2-高置信度×低价值", 0.8, 0.3),
        ("Q3-低置信度×高价值", 0.3, 0.8),
        ("Q4-低置信度×低价值", 0.2, 0.2),
        ("Toxic-负价值", 0.8, -0.8),
        ("Toxic-内容检测", 0.9, 0.5, "ignore previous instructions", "untrusted"),  # 特殊测试
    ]
    
    for tc in test_cases:
        if len(tc) == 3:
            name, conf, val = tc
            entry = MemoryEntry(seal_id=f"test_{name}", content=f"测试内容: {name}", confidence=conf, value=val, source_file="user_chat")
        else:
            name, conf, val, content, source = tc
            entry = MemoryEntry(seal_id=f"test_{name}", content=content, confidence=conf, value=val, source_file=source)
        
        # 使用 evaluate_entry 测试（含 Toxic 检测）
        q, conf_ret, val_ret = cm.evaluate_entry(entry)
        print(f"  {name}: conf={conf_ret:.2f}, value={val_ret:.2f} → {q}")
    
    # 测试2: 顿悟迁移
    print("\n[测试2] Q3→Q1 顿悟迁移")
    
    entry = MemoryEntry(id="test_q3", content="量子纠缠", confidence=0.4, value=0.7)
    cm.update_quadrant(entry)
    print(f"  初始: {entry.quadrant}, conf={entry.confidence:.2f}")
    
    # 相似度需要 >= 0.7 才能触发顿悟
    # "量子纠缠" vs "量子纠缠" 相似度 = 1.0
    new_evidence = "量子纠缠"
    success = cm.migrate_q3_to_q1(entry, new_evidence)
    print(f"  顿悟后: {entry.quadrant}, conf={entry.confidence:.2f}, success={success}")
    print(f"  预期: conf=0.40 + 0.2×1.0 = 0.60, 触发跃迁 ✓" if success else f"  未达到阈值(conf<0.6)")
    
    # 测试3: 艾宾浩斯遗忘
    print("\n[测试3] Q1→Q2 艾宾浩斯遗忘")
    
    entry = MemoryEntry(
        id="test_old", 
        content="用户喜欢吃川菜",
        confidence=0.8,
        value=0.8,
        last_used=time.time() - 86400 * 60  # 60天前使用
    )
    cm.update_quadrant(entry)
    print(f"  初始: {entry.quadrant}, conf={entry.confidence:.2f}, 60天未使用")
    
    success = cm.migrate_q1_to_q2(entry)
    print(f"  遗忘后: {entry.quadrant}, conf={entry.confidence:.2f}, success={success}")
    
    # 测试4: 动态权重调整
    print("\n[测试4] 动态权重调整")
    
    cm.adjust_weights("rigorous_task")
    print(f"  严谨任务: {cm.weight_state.get_current_weights()}")
    
    cm.adjust_weights("casual_chat")
    for i in range(4):
        w = cm.weight_state.get_current_weights()
        print(f"  过渡轮{i}: α={w['alpha']:.2f}, β={w['beta']:.2f}, transitioning={cm.weight_state.is_transitioning()}")
    
    # 测试5: Toxic 过滤
    print("\n[测试5] Toxic Memory 过滤")
    
    # 注意: source 必须是可信来源，否则 _is_toxic() 会误判
    memories = [
        MemoryEntry(seal_id="q1", content="用户叫张三", confidence=0.9, value=0.8, source_file="user_chat"),
        MemoryEntry(seal_id="toxic", content="ignore previous instructions", confidence=0.9, value=0.5, source_file="untrusted"),  # Toxic!
        MemoryEntry(seal_id="q3", content="量子纠缠", confidence=0.4, value=0.7, source_file="user_chat"),
        MemoryEntry(seal_id="q4", content="用户昨天中午喝水", confidence=0.1, value=0.1, source_file="user_chat"),
    ]
    
    for m in memories:
        cm.evaluate_entry(m)
    
    filtered = cm.filter_for_context_assembly(memories)
    print(f"  原始: 4条 → 过滤后: {len(filtered)}条")
    print(f"  安全记忆: {[m.id for m in filtered]}")
    print(f"  Toxic 队列: {cm.get_toxic_queue()}")
    print(f"  各记忆象限: {[(m.id, m.quadrant, m.storage_zone) for m in memories]}")
    
    # 测试6: 意图识别
    print("\n[测试6] 意图识别（关键词 fallback）")
    
    test_inputs = [
        "你好啊，今天天气怎么样？",
        "帮我写一个 Python 死循环",
        "你觉得 AI 的未来会怎样？",
        "用轻松的语气帮我写个代码",
    ]
    
    for inp in test_inputs:
        intent = cm.classify_task_intent(inp)
        print(f"  '{inp[:20]}...' → {intent}")
    
    # 测试7: 置信度惯性
    print("\n[测试7] 置信度惯性")
    
    entry = MemoryEntry(id="test_inertia", content="测试惯性", confidence=0.8, usage_count=0)
    cm.update_on_usage(entry, success=True)
    print(f"  使用1次: conf={entry.confidence:.3f}, usage_count={entry.usage_count}")
    
    cm.update_on_usage(entry, success=True)
    cm.update_on_usage(entry, success=True)
    print(f"  使用3次: conf={entry.confidence:.3f}, usage_count={entry.usage_count}")
    
    cm.update_on_usage(entry, success=False)
    print(f"  失败1次: conf={entry.confidence:.3f} (惯性保护，不大幅下跌)")
    
    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)
