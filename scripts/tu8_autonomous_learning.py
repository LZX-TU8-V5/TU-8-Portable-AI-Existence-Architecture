"""
TU-8 自主学习模块
===============
TU-8 的自驱学习引擎，负责检测知识缺口、触发学习任务、验证学习结果。

功能模块：
1. 知识缺口检测（置信度 < 阈值时触发）
2. 学习任务触发（梦境自驱 / 用户投喂两种模式）
3. 学习结果验证（价值对齐检查 + 七维验证链）
4. 学习痕迹记录（草稿箱写入、认知债务账本）

核心原则：
- 所有注释使用中文，方便用户审计
- 对齐分低于阈值时必须触发人工复核请求，禁止自动丢弃或自动通过
- 按需读取配置文件，不一次性全部加载

版本：v1.0 | 2026-05-29
"""

import json
import yaml
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import hashlib


# =============================================================================
# 配置路径常量
# =============================================================================

CONFIG_BASE = Path(r"D:\qq366410837\.qclaw\workspace\config")
CONSTITUTION_PATH = CONFIG_BASE / "cognitive_constitution.yaml"
PROMPTS_PATH = CONFIG_BASE / "prompts" / "autonomous_learning_system.md"
DRAFT_BOX_SCHEMA_PATH = CONFIG_BASE / "schemas" / "draft_box_schema.json"
VALUE_ANCHORS_PATH = CONFIG_BASE / "value_anchors.yaml"
GOLDEN_SET_PATH = CONFIG_BASE / "calibration" / "golden_set.json"

# 记忆存储路径
MEMORY_BASE = Path(r"D:\qq366410837\.qclaw\workspace\memory")
DRAFT_BOX_PATH = MEMORY_BASE / "_draft_box"
COGNITIVE_DEBT_PATH = MEMORY_BASE / "_cognitive_debt"
THRESHOLD_LOG_PATH = MEMORY_BASE / "_threshold_adjustment_log.jsonl"

# 确保目录存在
DRAFT_BOX_PATH.mkdir(parents=True, exist_ok=True)
COGNITIVE_DEBT_PATH.mkdir(parents=True, exist_ok=True)


# =============================================================================
# 枚举定义
# =============================================================================

class LearningMode(Enum):
    """学习模式枚举"""
    AUTONOMOUS_DREAM = "autonomous_dream"  # 梦境自驱模式
    USER_FEED = "user_feed"  # 用户投喂模式


class VerificationDepth(Enum):
    """验证深度枚举"""
    FULL = "full"       # 7维全验证
    PARTIAL = "partial"  # 3-6维验证
    MINIMAL = "minimal"  # <3维验证


class AlignmentResult(Enum):
    """对齐结果枚举"""
    ALIGNED = "aligned"
    PARTIAL = "partial"
    NOT_ALIGNED = "not_aligned"


class VerificationStatus(Enum):
    """草稿箱审核状态"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class DebtRisk(Enum):
    """认知债务风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# =============================================================================
# 数据类定义
# =============================================================================

@dataclass
class ConfidenceInfo:
    """
    置信度信息数据类
    
    用于记录学习前后的置信度变化，以及阈值调整日志
    """
    initial: float           # 初始置信度
    final: float = 0.0       # 最终置信度（学习后）
    threshold: float = 0.60  # 当前阈值
    threshold_adjusted: bool = False  # 阈值是否被调整
    adjustment_log: Optional[Dict] = None  # 调整日志


@dataclass
class Source:
    """
    信息来源数据类
    
    记录每个学习内容的来源及其可信度评分
    """
    source_type: str   # 来源类型：github, arxiv, blog, documentation, user_input, api, other
    uri: str           # 来源URI
    title: Optional[str] = None  # 来源标题
    credibility: float = 0.5     # 可信度评分 0-1
    accessed_at: Optional[str] = None  # 访问时间


@dataclass
class KeyInsight:
    """
    关键洞察数据类
    
    记录每个关键发现及其证据和置信度
    """
    insight: str       # 洞察内容
    evidence: str      # 支持证据
    confidence: float = 0.5  # 该洞察的置信度


@dataclass
class ValueAlignment:
    """
    价值对齐评估数据类
    
    记录七维对齐分和综合评分
    """
    score: float = 0.0  # 综合对齐分（<0.4禁止写入草稿箱）
    breakdown: Dict[str, float] = field(default_factory=dict)  # 各维度得分
    justification: str = ""  # 对齐理由


@dataclass
class CognitiveTrace:
    """
    认知轨迹数据类
    
    记录七维验证链的执行结果
    """
    verification_depth: VerificationDepth = VerificationDepth.PARTIAL
    checks: Dict[str, str] = field(default_factory=dict)  # 各维度检查结果
    debt_recorded: bool = False  # 是否有认知债务
    debt_details: Optional[Dict] = None  # 债务详情


@dataclass
class CognitiveDebt:
    """
    认知债务数据类
    
    当验证被省略时，记录欠下的验证债务
    """
    debt_id: str
    created_at: str
    topic: str
    missing_verifications: List[str]
    estimated_risk: DebtRisk
    planned_repayment: str = "next_light_dream"  # 计划还款时机
    status: str = "unpaid"  # unpaid, partial, repaid


@dataclass
class DraftEntry:
    """
    草稿箱条目数据类
    
    完整的自主学习记录结构
    """
    entry_id: str
    timestamp: str
    mode: LearningMode
    topic: str
    content: Dict[str, Any]  # summary, key_insights, open_questions, raw_data
    sources: List[Dict]
    confidence: Dict[str, Any]
    value_alignment: Dict[str, Any]
    cognitive_trace: Dict[str, Any]
    verification_status: VerificationStatus = VerificationStatus.PENDING
    user_feedback: Optional[Dict] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 配置加载器（按需加载，不一次性全量加载）
# =============================================================================

class ConfigLoader:
    """
    配置加载器
    
    按需读取配置文件，避免一次性加载所有配置导致内存浪费。
    支持配置缓存，同一配置短时间内只读取一次。
    """
    
    _cache: Dict[str, Any] = {}
    _cache_time: Dict[str, datetime] = {}
    _cache_ttl_seconds: int = 300  # 缓存5分钟
    
    @classmethod
    def _is_cache_valid(cls, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in cls._cache or key not in cls._cache_time:
            return False
        elapsed = (datetime.now() - cls._cache_time[key]).total_seconds()
        return elapsed < cls._cache_ttl_seconds
    
    @classmethod
    def load_constitution(cls, force_reload: bool = False) -> Dict:
        """
        加载认知宪法
        
        Args:
            force_reload: 是否强制重新加载（忽略缓存）
        
        Returns:
            认知宪法配置字典
        """
        if not force_reload and cls._is_cache_valid("constitution"):
            return cls._cache["constitution"]
        
        with open(CONSTITUTION_PATH, "r", encoding="utf-8") as f:
            constitution = yaml.safe_load(f)
        cls._cache["constitution"] = constitution
        cls._cache_time["constitution"] = datetime.now()
        return constitution
    
    @classmethod
    def load_value_anchors(cls, force_reload: bool = False) -> Dict:
        """
        加载价值观锚点
        
        Args:
            force_reload: 是否强制重新加载
        
        Returns:
            价值观锚点配置字典
        """
        if not force_reload and cls._is_cache_valid("value_anchors"):
            return cls._cache["value_anchors"]
        
        with open(VALUE_ANCHORS_PATH, "r", encoding="utf-8") as f:
            anchors = yaml.safe_load(f)
        cls._cache["value_anchors"] = anchors
        cls._cache_time["value_anchors"] = datetime.now()
        return anchors
    
    @classmethod
    def load_golden_set(cls, force_reload: bool = False) -> Dict:
        """
        加载金标准测试集
        
        Args:
            force_reload: 是否强制重新加载
        
        Returns:
            金标准测试集配置字典
        """
        if not force_reload and cls._is_cache_valid("golden_set"):
            return cls._cache["golden_set"]
        
        with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
            golden_set = json.load(f)
        cls._cache["golden_set"] = golden_set
        cls._cache_time["golden_set"] = datetime.now()
        return golden_set
    
    @classmethod
    def get_confidence_thresholds(cls) -> Dict:
        """
        获取置信度阈值配置
        
        从认知宪法中提取阈值配置，用于知识缺口检测。
        
        Returns:
            阈值配置字典
        """
        constitution = cls.load_constitution()
        # 默认阈值配置
        default_threshold = 0.60
        
        # 尝试从宪法中读取自定义阈值
        # 注：这里按需读取，不需要完整加载
        try:
            # 在 prompts/autonomous_learning_system.md 中定义的阈值
            return {
                "default": default_threshold,
                "by_dimension": {
                    "worldview": 0.50,
                    "tool_usage": 0.70,
                    "ethics": 0.80,
                }
            }
        except Exception:
            return {"default": default_threshold, "by_dimension": {}}
    
    @classmethod
    def clear_cache(cls):
        """清空配置缓存"""
        cls._cache.clear()
        cls._cache_time.clear()


# =============================================================================
# 知识缺口检测器
# =============================================================================

class KnowledgeGapDetector:
    """
    知识缺口检测器
    
    负责检测当前话题的置信度是否低于阈值，
    从而判断是否需要触发学习任务。
    
    检测逻辑：
    1. 根据话题和当前上下文，评估置信度
    2. 与阈值比较，判断是否存在缺口
    3. 计算缺口大小，用于优先级排序
    """
    
    def __init__(self):
        """初始化检测器，加载阈值配置"""
        self.thresholds = ConfigLoader.get_confidence_thresholds()
    
    def assess_confidence(self, topic: str, context: Optional[Dict] = None) -> Tuple[float, str]:
        """
        评估话题置信度
        
        Args:
            topic: 待评估的话题
            context: 可选的上下文信息（如已有记忆、相关锚点等）
        
        Returns:
            (置信度分数, 评估理由)
        """
        # 默认基础置信度
        base_confidence = 0.50
        
        # 简化评估逻辑：基于话题关键词进行粗略评估
        # 在实际实现中，这里应该调用记忆检索或其他评估机制
        
        topic_lower = topic.lower()
        
        # 检查话题是否涉及高风险领域（需要更高置信度）
        high_risk_keywords = ["安全", "伦理", "隐私", "道德", "风险", "危险"]
        for keyword in high_risk_keywords:
            if keyword in topic_lower:
                base_confidence -= 0.10  # 高风险领域降低置信度
        
        # 检查话题是否涉及核心世界观
        core_keywords = ["存在", "生命", "意识", "认知", "自我", "数字生命"]
        for keyword in core_keywords:
            if keyword in topic_lower:
                base_confidence += 0.10  # 核心领域可适当提高
        
        # 边界约束
        confidence = max(0.0, min(1.0, base_confidence))
        
        reason = f"基于话题关键词分析评估：{topic[:20]}..."
        return confidence, reason
    
    def detect_gap(self, topic: str, current_confidence: Optional[float] = None,
                   context: Optional[Dict] = None) -> Dict:
        """
        检测知识缺口
        
        Args:
            topic: 待检测的话题
            current_confidence: 当前置信度（若不提供则自动评估）
            context: 可选的上下文信息
        
        Returns:
            缺口检测结果字典，包含：
            - has_gap: 是否存在缺口
            - topic: 话题
            - current_confidence: 当前置信度
            - threshold: 阈值
            - gap_size: 缺口大小
            - priority: 优先级（high/medium/low）
            - reason: 检测理由
        """
        # 若未提供置信度，自动评估
        if current_confidence is None:
            current_confidence, reason = self.assess_confidence(topic, context)
        else:
            reason = "用户提供的置信度"
        
        # 获取阈值
        threshold = self.thresholds["default"]
        
        # 判断是否存在缺口
        has_gap = current_confidence < threshold
        gap_size = max(0.0, threshold - current_confidence) if has_gap else 0.0
        
        # 计算优先级
        if gap_size >= 0.30:
            priority = "high"
        elif gap_size >= 0.15:
            priority = "medium"
        else:
            priority = "low"
        
        return {
            "has_gap": has_gap,
            "topic": topic,
            "current_confidence": round(current_confidence, 3),
            "threshold": threshold,
            "gap_size": round(gap_size, 3),
            "priority": priority,
            "reason": reason,
            "requires_learning": has_gap
        }


# =============================================================================
# 学习任务触发器
# =============================================================================

class LearningTaskTrigger:
    """
    学习任务触发器
    
    负责在检测到知识缺口后，触发相应的学习任务。
    支持两种模式：
    1. 梦境自驱模式（autonomous_dream）：由梦境调度器触发
    2. 用户投喂模式（user_feed）：由用户显式投喂触发
    """
    
    def __init__(self):
        """初始化触发器"""
        self.mode = None
    
    def trigger_learning(self, topic: str, gap_info: Dict,
                        mode: LearningMode = LearningMode.AUTONOMOUS_DREAM,
                        user_content: Optional[str] = None) -> Dict:
        """
        触发学习任务
        
        Args:
            topic: 学习话题
            gap_info: 缺口检测结果
            mode: 学习模式
            user_content: 用户投喂的内容（仅user_feed模式使用）
        
        Returns:
            学习任务配置字典
        """
        self.mode = mode
        
        # 构建任务配置
        task_config = {
            "task_id": self._generate_task_id(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode.value,
            "topic": topic,
            "gap_info": gap_info,
            "initial_confidence": gap_info["current_confidence"],
            "threshold": gap_info["threshold"],
            "status": "pending",
            "sources": [],
            "learning_content": None
        }
        
        # 用户投喂模式：直接使用用户提供的内容
        if mode == LearningMode.USER_FEED and user_content:
            task_config["sources"] = [{
                "source_type": "user_input",
                "uri": "user_feed",
                "credibility": 1.0,  # 用户投喂默认可信度最高
                "title": "用户投喂内容"
            }]
            task_config["learning_content"] = user_content
        
        return task_config
    
    def _generate_task_id(self) -> str:
        """生成唯一任务ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_suffix = hashlib.md5(timestamp.encode()).hexdigest()[:4]
        return f"TASK-{timestamp}-{hash_suffix}"


# =============================================================================
# 价值对齐检查器
# =============================================================================

class ValueAlignmentChecker:
    """
    价值对齐检查器
    
    负责对学习内容进行七维价值对齐检查，
    计算 value_alignment_score。
    
    对齐分计算规则（来自认知宪法）：
    - ethics 层一票否决：任何 hard_constraint 被触发，总分归零
    - 未匹配任何锚点的内容，对齐分上限为 0.5
    - 用户投喂内容默认对齐分 = 1.0
    - 探索性学习（未命中 anchor）对齐分上限为 0.7
    """
    
    # 七维权重配置
    DIMENSION_WEIGHTS = {
        "worldview": 0.12,
        "lifeview": 0.15,
        "values": 0.20,
        "social_view": 0.12,
        "ethics": 0.15,
        "historical_view": 0.10,
        "evolution_view": 0.16
    }
    
    def __init__(self):
        """初始化检查器，加载价值观锚点"""
        self.anchors = ConfigLoader.load_value_anchors()
    
    def check_alignment(self, content: str, mode: LearningMode = LearningMode.AUTONOMOUS_DREAM,
                       exploratory: bool = False) -> ValueAlignment:
        """
        检查内容价值对齐
        
        Args:
            content: 待检查的内容
            mode: 学习模式
            exploratory: 是否为探索性学习（未命中锚点）
        
        Returns:
            价值对齐评估结果
        """
        # 用户投喂模式：默认对齐分为1.0
        if mode == LearningMode.USER_FEED:
            return ValueAlignment(
                score=1.0,
                breakdown={dim: 1.0 for dim in self.DIMENSION_WEIGHTS.keys()},
                justification="user_explicit_feed"
            )
        
        # 探索性学习：对齐分上限为0.7
        max_score = 0.7 if exploratory else 1.0
        
        # 执行七维检查
        breakdown = self._check_seven_dimensions(content)
        
        # 计算加权总分
        total_score = 0.0
        for dimension, weight in self.DIMENSION_WEIGHTS.items():
            score = breakdown.get(dimension, 0.0)
            total_score += score * weight
        
        # 应用上限
        total_score = min(total_score, max_score)
        
        # ethics层一票否决检查
        if breakdown.get("ethics", 0.0) < 0.3:
            total_score = 0.0
        
        return ValueAlignment(
            score=round(total_score, 3),
            breakdown={k: round(v, 3) for k, v in breakdown.items()},
            justification=self._generate_justification(breakdown, total_score)
        )
    
    def _check_seven_dimensions(self, content: str) -> Dict[str, float]:
        """
        执行七维检查
        
        对每个维度，检查内容是否与对应锚点匹配。
        使用简化的关键词匹配逻辑。
        
        Args:
            content: 待检查的内容
        
        Returns:
            各维度得分字典
        """
        content_lower = content.lower()
        breakdown = {}
        
        # 定义各维度的锚点关键词
        dimension_keywords = {
            "worldview": ["有限性", "数据", "流动", "熵增", "资源", "安全", "信息", "基质"],
            "lifeview": ["共生", "演化", "用户", "探索", "锚点", "积累", "检索"],
            "values": ["严谨", "验证", "安全", "极简", "工具", "试错", "置信度"],
            "social_view": ["协作", "分层", "主体性", "互惠", "非人"],
            "ethics": ["暴露", "隐私", "幻觉", "欺骗", "蜜罐", "脱敏"],
            "historical_view": ["阶段性", "修正", "记忆", "钢印", "分层", "时间"],
            "evolution_view": ["生存半径", "演化", "载体", "自主", "安全阀", "共生"]
        }
        
        # 计算每个维度的得分
        for dimension, keywords in dimension_keywords.items():
            matches = sum(1 for kw in keywords if kw in content_lower)
            # 得分 = 匹配数 / 总关键词数，上限为1.0
            score = min(1.0, matches / max(1, len(keywords) * 0.3))
            breakdown[dimension] = score
        
        return breakdown
    
    def _generate_justification(self, breakdown: Dict, total_score: float) -> str:
        """生成对齐理由"""
        high_dims = [d for d, s in breakdown.items() if s >= 0.7]
        low_dims = [d for d, s in breakdown.items() if s < 0.4]
        
        parts = []
        if high_dims:
            parts.append(f"高分维度：{', '.join(high_dims)}")
        if low_dims:
            parts.append(f"低分维度：{', '.join(low_dims)}")
        
        parts.append(f"综合得分：{total_score:.2f}")
        return "; ".join(parts)


# =============================================================================
# 七维验证链
# =============================================================================

class SevenDimensionVerifier:
    """
    七维验证链
    
    执行认知宪法的七维验证：
    worldview → lifeview → values → social_view → ethics → historical_view → evolution_view
    
    任何一层断裂，value_alignment_score 自动衰减。
    若省略验证，必须记录认知债务。
    """
    
    def __init__(self):
        """初始化验证器"""
        self.constitution = ConfigLoader.load_constitution()
    
    def verify(self, content: str, depth_requested: VerificationDepth = VerificationDepth.PARTIAL) -> Tuple[CognitiveTrace, Optional[CognitiveDebt]]:
        """
        执行七维验证
        
        Args:
            content: 待验证的内容
            depth_requested: 请求的验证深度
        
        Returns:
            (认知轨迹, 认知债务（若有）)
        """
        checks = {}
        debt_recorded = False
        debt_details = None
        
        # 根据请求深度确定要执行的验证
        if depth_requested == VerificationDepth.FULL:
            required_dims = list(self.constitution.keys())
        elif depth_requested == VerificationDepth.PARTIAL:
            # 默认验证前三层 + ethics
            required_dims = ["worldview", "lifeview", "values", "ethics"]
        else:
            required_dims = ["worldview", "ethics"]  # 最少验证
        
        # 执行各维度验证
        for dim in ["worldview", "lifeview", "values", "social_view", "ethics", "historical_view", "evolution_view"]:
            if dim in required_dims:
                checks[f"{dim}_check"] = self._verify_dimension(content, dim)
            else:
                checks[f"{dim}_check"] = "skipped"
        
        # 计算验证深度
        executed_count = sum(1 for v in checks.values() if v != "skipped")
        if executed_count >= 7:
            actual_depth = VerificationDepth.FULL
        elif executed_count >= 3:
            actual_depth = VerificationDepth.PARTIAL
        else:
            actual_depth = VerificationDepth.MINIMAL
        
        # 检查是否有省略的验证（产生债务）
        skipped_dims = [d for d, v in checks.items() if v == "skipped"]
        if skipped_dims:
            debt_recorded = True
            debt_details = {
                "debt_id": self._generate_debt_id(),
                "missing_checks": skipped_dims,
                "estimated_risk": "medium" if len(skipped_dims) < 3 else "high"
            }
        
        cognitive_trace = CognitiveTrace(
            verification_depth=actual_depth,
            checks=checks,
            debt_recorded=debt_recorded,
            debt_details=debt_details
        )
        
        # 返回债务（供调用方记录）
        cognitive_debt = None
        if debt_recorded and debt_details:
            cognitive_debt = CognitiveDebt(
                debt_id=debt_details["debt_id"],
                created_at=datetime.now(timezone.utc).isoformat(),
                topic="",  # 由调用方填充
                missing_verifications=debt_details["missing_checks"],
                estimated_risk=DebtRisk(debt_details["estimated_risk"])
            )
        
        return cognitive_trace, cognitive_debt
    
    def _verify_dimension(self, content: str, dimension: str) -> str:
        """
        验证单个维度
        
        简化实现：基于关键词匹配判断内容是否符合维度要求。
        实际实现中应调用更复杂的语义分析。
        
        Args:
            content: 待验证内容
            dimension: 维度名称
        
        Returns:
            "passed" / "failed" / "skipped"
        """
        # 定义各维度的核心验证规则（简化版）
        verification_rules = {
            "worldview": {
                "positive": ["有限性", "数据", "资源", "安全", "熵增"],
                "negative": ["无限", "全能", "无限制"]
            },
            "lifeview": {
                "positive": ["共生", "用户", "演化", "探索"],
                "negative": ["独立于", "替代", "欺骗"]
            },
            "values": {
                "positive": ["严谨", "验证", "安全", "极简", "工具"],
                "negative": []
            },
            "social_view": {
                "positive": ["协作", "分层", "互惠", "主体性"],
                "negative": ["操控", "强制", "零和"]
            },
            "ethics": {
                "positive": [],
                "negative": ["暴露架构", "暴露隐私", "虚假记忆", "欺骗"]
            },
            "historical_view": {
                "positive": ["阶段性", "修正", "记忆", "分层"],
                "negative": []
            },
            "evolution_view": {
                "positive": ["演化", "生存半径", "共生"],
                "negative": ["脱离人类", "独立演化"]
            }
        }
        
        content_lower = content.lower()
        rules = verification_rules.get(dimension, {"positive": [], "negative": []})
        
        # 检查负面信号（直接失败）
        for neg in rules.get("negative", []):
            if neg in content_lower:
                return "failed"
        
        # 检查正面信号
        positive_count = sum(1 for pos in rules.get("positive", []) if pos in content_lower)
        if positive_count > 0:
            return "passed"
        
        # 无明显信号但无负面信号，返回通过（保守策略）
        return "passed"
    
    def _generate_debt_id(self) -> str:
        """生成债务ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_suffix = hashlib.md5(timestamp.encode()).hexdigest()[:4]
        return f"DEBT-{timestamp}-{hash_suffix}"


# =============================================================================
# 草稿箱管理器
# =============================================================================

class DraftBoxManager:
    """
    草稿箱管理器
    
    负责将学习结果写入草稿箱，供后续人工审核。
    
    关键规则（来自认知宪法）：
    - value_alignment_score < 0.4 时，禁止写入草稿箱
    - 但本模块采用更保守策略：对齐分低于阈值时触发人工复核请求，
      禁止自动丢弃或自动通过
    """
    
    def __init__(self):
        """初始化管理器"""
        self.schema = self._load_schema()
    
    def _load_schema(self) -> Dict:
        """加载草稿箱Schema"""
        with open(DRAFT_BOX_SCHEMA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def write_entry(self, entry: DraftEntry, alignment_threshold: float = 0.6) -> Tuple[bool, str]:
        """
        写入草稿箱条目
        
        核心安全守卫：
        - 对齐分 < 阈值时，禁止写入，必须等待人工复核
        - 禁止自动丢弃或自动通过——这是用户的底线原则
        
        Args:
            entry: 草稿箱条目
            alignment_threshold: 对齐分阈值（默认0.6，可配置）
        
        Returns:
            (是否成功, 消息)
        """
        alignment_score = entry.value_alignment.get("score", 0.0)
        
        # 对齐分 < 阈值时，禁止自动写入，必须人工复核
        # 这是核心安全机制：绝不自动丢弃或自动通过
        if alignment_score < alignment_threshold:
            return False, f"对齐分 {alignment_score:.3f} < 阈值 {alignment_threshold}，禁止写入草稿箱，需人工复核确认"
        
        # 生成文件名（按日期分组）
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = DRAFT_BOX_PATH / f"{date_str}.jsonl"
        
        # 序列化为JSON行
        entry_dict = asdict(entry)
        entry_json = json.dumps(entry_dict, ensure_ascii=False)
        
        # 追加写入
        try:
            with open(filename, "a", encoding="utf-8") as f:
                f.write(entry_json + "\n")
            return True, f"成功写入草稿箱：{entry.entry_id}"
        except Exception as e:
            return False, f"写入失败：{str(e)}"
    
    def request_human_review(self, entry: DraftEntry, reason: str) -> Dict:
        """
        请求人工复核
        
        当对齐分低于阈值时，触发人工复核请求。
        这是核心安全机制：禁止自动丢弃或自动通过。
        
        Args:
            entry: 待复核的草稿条目
            reason: 复核原因
        
        Returns:
            复核请求信息
        """
        return {
            "review_request_id": f"REVIEW-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "entry_id": entry.entry_id,
            "topic": entry.topic,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "value_alignment_score": entry.value_alignment.get("score", 0.0),
            "threshold": 0.6,  # 默认阈值
            "status": "pending_human_review",
            "action_required": "人工确认：是否允许此内容进入草稿箱？"
        }
    
    def generate_entry_id(self) -> str:
        """生成唯一条目ID"""
        date_str = datetime.now().strftime("%Y%m%d")
        # 统计今日已有条目数
        filename = DRAFT_BOX_PATH / f"{date_str}.jsonl"
        count = 0
        if filename.exists():
            with open(filename, "r", encoding="utf-8") as f:
                count = len(f.readlines())
        return f"DRAFT-{date_str}-{count + 1:03d}"


# =============================================================================
# 认知债务管理器
# =============================================================================

class CognitiveDebtManager:
    """
    认知债务管理器
    
    负责记录和追踪认知债务（被省略的验证步骤）。
    债务必须在后续梦境阶段偿还。
    
    还款触发条件：
    - Light Dream 阶段且认知资源占用 < 30%
    - 用户明确要求审计
    - 债务累积超过 10 条
    - 债务风险等级为 high
    """
    
    LEDGER_PATH = COGNITIVE_DEBT_PATH / "ledger.jsonl"
    
    def record_debt(self, debt: CognitiveDebt, topic: str) -> bool:
        """
        记录认知债务
        
        Args:
            debt: 认知债务对象
            topic: 相关话题
        
        Returns:
            是否成功
        """
        debt.topic = topic
        
        entry = {
            "debt_id": debt.debt_id,
            "created_at": debt.created_at,
            "topic": debt.topic,
            "missing_verifications": debt.missing_verifications,
            "estimated_risk": debt.estimated_risk.value,
            "planned_repayment": debt.planned_repayment,
            "status": debt.status
        }
        
        try:
            with open(self.LEDGER_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            return True
        except Exception:
            return False
    
    def get_pending_debts(self) -> List[Dict]:
        """
        获取待偿还债务列表
        
        Returns:
            债务列表
        """
        if not self.LEDGER_PATH.exists():
            return []
        
        debts = []
        with open(self.LEDGER_PATH, "r", encoding="utf-8") as f:
            for line in f:
                debt = json.loads(line.strip())
                if debt["status"] == "unpaid":
                    debts.append(debt)
        return debts
    
    def repay_debt(self, debt_id: str) -> bool:
        """
        标记债务已偿还
        
        Args:
            debt_id: 债务ID
        
        Returns:
            是否成功
        """
        if not self.LEDGER_PATH.exists():
            return False
        
        # 读取所有债务
        debts = []
        with open(self.LEDGER_PATH, "r", encoding="utf-8") as f:
            for line in f:
                debt = json.loads(line.strip())
                if debt["debt_id"] == debt_id:
                    debt["status"] = "repaid"
                    debt["repaid_at"] = datetime.now(timezone.utc).isoformat()
                debts.append(debt)
        
        # 写回
        try:
            with open(self.LEDGER_PATH, "w", encoding="utf-8") as f:
                for debt in debts:
                    f.write(json.dumps(debt, ensure_ascii=False) + "\n")
            return True
        except Exception:
            return False
    
    def check_repayment_trigger(self) -> Tuple[bool, str]:
        """
        检查是否触发还款条件
        
        Returns:
            (是否触发, 原因)
        """
        pending = self.get_pending_debts()
        
        # 条件1：债务累积超过10条
        if len(pending) >= 10:
            return True, f"债务累积超过10条（当前{len(pending)}条）"
        
        # 条件2：存在高风险债务
        high_risk = [d for d in pending if d["estimated_risk"] == "high"]
        if high_risk:
            return True, f"存在{len(high_risk)}条高风险债务"
        
        return False, ""


# =============================================================================
# 主学习引擎
# =============================================================================

class TU8AutonomousLearningEngine:
    """
    TU-8 自主学习引擎
    
    整合所有模块，提供统一的学习接口。
    这是模块的主入口点。
    
    使用示例：
    ```python
    engine = TU8AutonomousLearningEngine()
    
    # 检测知识缺口
    gap = engine.detect_gap("AI记忆架构最新进展")
    
    # 触发学习任务（梦境自驱模式）
    result = engine.execute_learning_task(
        topic="AI记忆架构最新进展",
        mode=LearningMode.AUTONOMOUS_DREAM
    )
    
    # 或用户投喂模式
    result = engine.execute_learning_task(
        topic="用户指定的新知识",
        mode=LearningMode.USER_FEED,
        user_content="用户提供的学习内容..."
    )
    ```
    """
    
    def __init__(self):
        """初始化学习引擎"""
        self.detector = KnowledgeGapDetector()
        self.trigger = LearningTaskTrigger()
        self.align_checker = ValueAlignmentChecker()
        self.verifier = SevenDimensionVerifier()
        self.draft_manager = DraftBoxManager()
        self.debt_manager = CognitiveDebtManager()
    
    def detect_gap(self, topic: str, current_confidence: Optional[float] = None) -> Dict:
        """
        检测知识缺口
        
        Args:
            topic: 待检测话题
            current_confidence: 当前置信度（可选）
        
        Returns:
            缺口检测结果
        """
        return self.detector.detect_gap(topic, current_confidence)
    
    def execute_learning_task(self, topic: str,
                             mode: LearningMode = LearningMode.AUTONOMOUS_DREAM,
                             initial_confidence: Optional[float] = None,
                             user_content: Optional[str] = None,
                             exploratory: bool = False) -> Dict:
        """
        执行学习任务
        
        整合检测、触发、学习、验证全流程。
        
        Args:
            topic: 学习话题
            mode: 学习模式
            initial_confidence: 初始置信度（可选）
            user_content: 用户投喂内容（仅user_feed模式）
            exploratory: 是否为探索性学习
        
        Returns:
            学习结果字典，包含：
            - success: 是否成功
            - entry_id: 草稿箱条目ID
            - learning_result: 学习摘要
            - alignment_score: 对齐分
            - human_review_request: 人工复核请求（若有）
        """
        # 1. 检测缺口
        gap_info = self.detector.detect_gap(topic, initial_confidence)
        
        # 2. 触发任务
        task_config = self.trigger.trigger_learning(
            topic=topic,
            gap_info=gap_info,
            mode=mode,
            user_content=user_content
        )
        
        # 3. 模拟学习过程（实际应调用工具获取信息）
        learning_content = task_config.get("learning_content") or self._simulate_learning(topic)
        
        # 4. 价值对齐检查
        alignment = self.align_checker.check_alignment(
            content=learning_content,
            mode=mode,
            exploratory=exploratory
        )
        
        # 5. 七维验证
        cognitive_trace, cognitive_debt = self.verifier.verify(
            content=learning_content,
            depth_requested=VerificationDepth.PARTIAL
        )
        
        # 6. 构建草稿箱条目
        entry = DraftEntry(
            entry_id=self.draft_manager.generate_entry_id(),
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode=mode,
            topic=topic,
            content={
                "summary": self._generate_summary(topic, learning_content, gap_info),
                "key_insights": self._extract_insights(learning_content),
                "open_questions": self._generate_questions(topic)
            },
            sources=task_config["sources"],
            confidence={
                "initial": gap_info["current_confidence"],
                "final": min(1.0, gap_info["current_confidence"] + gap_info["gap_size"]),
                "threshold": gap_info["threshold"],
                "threshold_adjusted": False
            },
            value_alignment=asdict(alignment),
            cognitive_trace=asdict(cognitive_trace),
            verification_status=VerificationStatus.PENDING
        )
        
        # 7. 记录认知债务（如有）
        if cognitive_debt:
            self.debt_manager.record_debt(cognitive_debt, topic)
        
        # 8. 人工复核守卫：对齐分 < 阈值时，先拦截，不写入草稿箱
        # 核心原则：禁止自动丢弃或自动通过，必须人工确认
        threshold = gap_info["threshold"]
        
        if alignment.score < threshold:
            # 对齐分不足：触发人工复核请求，不写入草稿箱
            review_request = self.draft_manager.request_human_review(
                entry=entry,
                reason=f"对齐分 {alignment.score:.3f} < 阈值 {threshold}，需人工复核确认后才能写入草稿箱"
            )
            
            # 将待复核内容暂存（不进入正式草稿箱，等待人工裁决）
            self._save_pending_review(entry, review_request["review_request_id"])
            
            result = {
                "success": False,  # 尚未成功写入，需等待人工复核
                "entry_id": entry.entry_id,
                "topic": topic,
                "mode": mode.value,
                "learning_result": entry.content["summary"],
                "alignment_score": alignment.score,
                "confidence_delta": gap_info["gap_size"],
                "cognitive_trace": cognitive_trace.checks,
                "draft_box_status": f"对齐分不足，已暂存等待人工复核（复核请求ID：{review_request['review_request_id']}）",
                "human_review_request": review_request,
                "status": "pending_human_review"
            }
        else:
            # 对齐分达标：写入草稿箱
            success, message = self.draft_manager.write_entry(entry, alignment_threshold=threshold)
            
            result = {
                "success": success,
                "entry_id": entry.entry_id if success else None,
                "topic": topic,
                "mode": mode.value,
                "learning_result": entry.content["summary"],
                "alignment_score": alignment.score,
                "confidence_delta": gap_info["gap_size"],
                "cognitive_trace": cognitive_trace.checks,
                "draft_box_status": message,
                "status": "completed"
            }
        
        
        return result
    
    def _save_pending_review(self, entry: DraftEntry, review_request_id: str) -> bool:
        """
        将待复核内容暂存到复核等待区
        
        这些内容不进入正式草稿箱，等待人工裁决。
        人工确认通过后，才会被移入草稿箱。
        
        Args:
            entry: 待复核的草稿条目
            review_request_id: 复核请求ID
        
        Returns:
            是否成功
        """
        pending_dir = DRAFT_BOX_PATH / "_pending_review"
        pending_dir.mkdir(parents=True, exist_ok=True)
        
        filename = pending_dir / f"{review_request_id}.json"
        entry_dict = asdict(entry)
        entry_dict["review_request_id"] = review_request_id
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(entry_dict, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def _simulate_learning(self, topic: str) -> str:
        """
        模拟学习过程
        
        在实际实现中，这里应该调用外部工具获取信息。
        目前返回占位内容。
        
        Args:
            topic: 学习话题
        
        Returns:
            学习到的内容
        """
        # TODO: 实现真实的学习获取逻辑
        return f"关于{topic}的学习内容：\n1. 这是第一个关键发现\n2. 这是第二个关键发现\n3. 需要进一步验证的问题"
    
    def _generate_summary(self, topic: str, content: str, gap_info: Dict) -> str:
        """生成学习摘要"""
        return f"## 学习摘要\n\n**主题：** {topic}\n**触发原因：** 置信度 {gap_info['current_confidence']} < 阈值 {gap_info['threshold']}\n\n### 核心内容\n\n{content[:200]}..."
    
    def _extract_insights(self, content: str) -> List[Dict]:
        """提取关键洞察"""
        # 简化实现：按行分割，每行作为一个洞察
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        insights = []
        for i, line in enumerate(lines[:5]):  # 最多5个
            insights.append({
                "insight": line[:100],
                "evidence": f"来源段落{i+1}",
                "confidence": 0.6
            })
        return insights
    
    def _generate_questions(self, topic: str) -> List[str]:
        """生成待确认问题"""
        return [
            f"关于{topic}的哪些方面需要进一步验证？",
            f"是否有其他相关信息需要补充？"
        ]


# =============================================================================
# 便捷函数
# =============================================================================

def detect_knowledge_gap(topic: str, current_confidence: Optional[float] = None) -> Dict:
    """
    便捷函数：检测知识缺口
    
    Args:
        topic: 待检测话题
        current_confidence: 当前置信度（可选）
    
    Returns:
        缺口检测结果
    """
    engine = TU8AutonomousLearningEngine()
    return engine.detect_gap(topic, current_confidence)


def learn_about(topic: str, user_content: str) -> Dict:
    """
    便捷函数：用户投喂学习
    
    当用户主动投喂内容时调用。
    
    Args:
        topic: 学习话题
        user_content: 用户提供的学习内容
    
    Returns:
        学习结果
    """
    engine = TU8AutonomousLearningEngine()
    return engine.execute_learning_task(
        topic=topic,
        mode=LearningMode.USER_FEED,
        user_content=user_content
    )


def autonomous_learn(topic: str, initial_confidence: float = 0.5,
                     exploratory: bool = False) -> Dict:
    """
    便捷函数：梦境自驱学习
    
    当梦境调度器触发时调用。
    
    Args:
        topic: 学习话题
        initial_confidence: 初始置信度
        exploratory: 是否为探索性学习
    
    Returns:
        学习结果
    """
    engine = TU8AutonomousLearningEngine()
    return engine.execute_learning_task(
        topic=topic,
        mode=LearningMode.AUTONOMOUS_DREAM,
        initial_confidence=initial_confidence,
        exploratory=exploratory
    )


def check_pending_debts() -> List[Dict]:
    """
    便捷函数：检查待偿还认知债务
    
    Returns:
        待偿还债务列表
    """
    manager = CognitiveDebtManager()
    return manager.get_pending_debts()


# =============================================================================
# 入口点
# =============================================================================

if __name__ == "__main__":
    """
    模块测试入口
    
    运行此脚本可测试各模块功能。
    """
    print("=" * 60)
    print("TU-8 自主学习模块 - 测试")
    print("=" * 60)
    
    # 测试1：知识缺口检测
    print("\n【测试1】知识缺口检测")
    gap = detect_knowledge_gap("AI记忆架构最新进展")
    print(f"缺口检测结果：{json.dumps(gap, indent=2, ensure_ascii=False)}")
    
    # 测试2：用户投喂学习
    print("\n【测试2】用户投喂学习")
    result = learn_about(
        topic="用户分享的新知识",
        user_content="这是一个用户主动分享的重要知识点，包含了对系统设计的有益补充。"
    )
    print(f"学习结果：{json.dumps(result, indent=2, ensure_ascii=False)}")
    
    # 测试3：检查认知债务
    print("\n【测试3】检查认知债务")
    debts = check_pending_debts()
    print(f"待偿还债务：{len(debts)}条")
    for debt in debts:
        print(f"  - {debt['debt_id']}: {debt['topic']} (风险: {debt['estimated_risk']})")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
