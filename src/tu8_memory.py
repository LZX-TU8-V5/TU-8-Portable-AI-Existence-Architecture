# tu8_memory.py - TU-8 记忆系统核心
# 版本：v2.1 | 日期：2026-06-06 | 基于OpenClaw记忆系统逆向成果 + 12篇前沿论文吸收
# 标签：#记忆蒸馏 #三层梦境 #双路检索 #六维晋升 #干扰驱动遗忘 #GracefulDegradation #双阶段睡眠 #环境漂移验证 #干扰熵 #认知事件边界
#
# v2.1 变更日志（基于12篇论文优化）：
#   P0: 干扰熵度量（Barman 2026 “The Price of Meaning”）—— 语义记忆泛化-遗忘 tradeoff 形式化
#   P0: 认知事件边界检测（Ahmad 2605.31473 ES+MNA）—— dream_check() 从纯时间驱动升级为事件驱动
#   P1: PI对数线性动态惩罚（Xie 2026 “Learning to Forget”）—— PI_PRIORITY_BOOST 从固定值升级为动态公式
#   P1: PI>RI 差异化冲突阈值（Chattaraj & Raj 2026 “Transformers Remember First”）—— PI使用更低的冲突阈值
#   --- v2.0 基线 ---
#   P0: 干扰驱动遗忘门（SleepGate 2603.14517）—— forget() 从规则驱动升级为冲突感知
#   P0: Graceful Degradation 6级保真降级（2605.08538 §5）—— 替代直接删除
#   P1: REM/NREM 双阶段睡眠（SCM 2604.20943）—— dream_check() 改造
#   P1: PI前摄干扰优先处理（2603.00270）—— 遗忘门内嵌PI检测
#   P1: 记忆-环境漂移验证（GLOVE 2601.19249）—— 新增 DriftVerifier
#   P1: Temporal Validation 乱序检测（2605.08538 §4）—— 新增乱序检测器

# =============================================================================
# TU-8 L0-L6 架构层标注
# =============================================================================
# L0 存在   ─── WORKSPACE 路径、文件读写安全边界
# L1 认知   ─── PI_PRIORITY_BOOST 动态公式、干扰熵阈值
# L2 方法论 ─── store()、recall()、forget()、dream_check() 核心 API
# L3 架构   ─── 三层记忆结构（L1短期/L2中期/L3长期）、晋升/遗忘门
# L4 协作   ─── MemoryAdapter（与 consciousness_cycle 桥接）
# L5 钢印   ─── 钢印链写入（store → seal_chain）
# L6 健康   ─── Graceful Degradation 六级降级、DriftVerifier 环境漂移检测
#
# 代谢归属：记忆代谢（管道）→ metabolic_pipeline.py + memory_gc.py
# 代谢接口：dream_check() → run_full_metabolism_cycle()
# =============================================================================

import os
import re
import json
import math
import time
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from abc import ABC, abstractmethod
from pathlib import Path
import threading
import sys
import cog_filters  # 认知过滤器：TimeFactor × Confidence × InfoDensity

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Windows GBK 终端兼容：强制 stdout/stderr UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# =============================================================================
# 常量定义
# =============================================================================

DEFAULT_PROMOTION_WEIGHTS = {
    "freq": 0.20,      # 召回频率
    "rel": 0.25,      # 相关性
    "div": 0.12,      # 独特性
    "rec": 0.12,      # 时效性
    "cons": 0.08,     # 巩固度
    "conc": 0.05,     # 概念丰富度
    "meaning": 0.10,  # 意义锚定（TU-8新增）
    "emotion": 0.08   # 情感灼刻（TU-8新增）
}

DEFAULT_PROMOTION_MIN_SCORE = 0.75  # 晋升阈值
PROMOTION_HALF_LIFE_DAYS = 14       # 半衰期

# =============================================================================
# v2.0 新增常量：干扰驱动遗忘 + Graceful Degradation
# =============================================================================

# --- SleepGate 冲突感知遗忘门 (2603.14517) ---
CONFLICT_SIMILARITY_THRESHOLD = 0.70  # 冲突相似度阈值（高于此值视为潜在冲突）
CONFLICT_CONTRADICTION_PATTERNS = [  # 矛盾信号模式
    (r"不是(.{1,20})而是", "否定修正"),
    (r"(已|已不|不再|不再有)", "状态变更"),
    (r"(错误|不对|修正|更正|纠正)", "纠错信号"),
    (r"(以前|之前|过去).{0,10}(现在|如今|目前)", "时间对比"),
]
PI_PRIORITY_BOOST_BASE = 0.3    # PI优先遗忘基础加成（2603.00270）
PI_LOG_LINEAR_RATE = 0.15       # PI对数线性衰减率（Xie 2026 “Learning to Forget”）
PI_CONFLICT_THRESHOLD = 0.55    # PI专用冲突阈值（低于通用0.70，因为PI>RI, Chattaraj & Raj 2026）
RI_CONFLICT_THRESHOLD = 0.70    # RI专用冲突阈值（保持原值）

# --- 干扰熵度量 (Barman 2026 "The Price of Meaning") ---
INTERFERENCE_ENTROPY_BASELINE = 0.1   # 干扰熵基线（无冲突时的基准值）
INTERFERENCE_ENTROPY_MAX = 2.0        # 干扰熵上限
INTERFERENCE_ENTROPY_DEGRADE_K = 0.5   # 干扰熵→降级概率的缩放系数
CONFLICT_CANDIDATE_WINDOW = 20          # 冲突检测窗口：每标签只与最近N条比较

# --- 认知事件边界检测 (Ahmad 2605.31473 ES+MNA) ---
EVENT_BOUNDARY_ENABLED = True         # 启用事件边界驱动的梦境触发
# EVENT_BOUNDARY_SURPRISE_THRESHOLD = 0.6  # v2.1a: 已移除（surprise信号无数据支撑）
EVENT_BOUNDARY_TAG_SHIFT_THRESHOLD = 0.5 # 标签分布偏移阈值
EVENT_BOUNDARY_MIN_INTERVAL = 1800      # 事件边界触发梦境的最小间隔（秒，30分钟）
EVENT_BOUNDARY_PEEK_WINDOW = 5          # 边界检测回看窗口（最近N条写入）

# --- Graceful Degradation 6级保真降级 (2605.08538 §5) ---
FIDELITY_LEVELS = {
    0: {"name": "L0_FULL",       "retention": 1.00, "desc": "完整保留"},
    1: {"name": "L1_SUMMARY",    "retention": 0.75, "desc": "摘要保留（关键词+时间+标签）"},
    2: {"name": "L2_KEY_POINTS",  "retention": 0.50, "desc": "关键点保留（3-5个核心要素）"},
    3: {"name": "L3_SEMANTIC",    "retention": 0.25, "desc": "语义骨架（主题+情感+关系）"},
    4: {"name": "L4_GHOST",       "retention": 0.10, "desc": "幽灵标记（存在感+锚点引用）"},
    5: {"name": "L5_TOMBSTONE",   "retention": 0.00, "desc": "墓碑（仅ID+删除时间+原因）"},
}
DEGRADATION_RECALL_THRESHOLD = 0.15  # 低于此召回率的记忆触发降级评估
DEGRADATION_CONFLICT_PENALTY = 0.2   # 冲突记忆额外降级惩罚

# --- REM/NREM 双阶段睡眠 (SCM 2604.20943) ---
NREM_INTERVAL = 4 * 3600       # NREM: 每4小时（浅度整合+巩固度更新）
REM_INTERVAL = 24 * 3600       # REM: 每24小时（深度整合+钢印+灵感生成）
NREM_NOISE_REDUCTION_TARGET = 0.90  # NREM目标噪声减少率

# --- GLOVE 环境漂移验证 (2601.19249) ---
DRIFT_VERIFICATION_INTERVAL = 7 * 86400  # 每7天验证一次环境一致性
DRIFT_SIMILARITY_THRESHOLD = 0.6        # 低于此值触发 Active Probing

# --- Temporal Validation (2605.08538 §4) ---
TEMPORAL_ANOMALY_WINDOW = 300   # 5分钟内同一主题多次写入视为乱序异常

# 三层梦境周期（秒）
LIGHT_DREAM_INTERVAL = 6 * 3600     # 6小时
DEEP_DREAM_HOUR = 3                 # 每天凌晨3点
REM_DREAM_WEEKDAY = 6               # 周日

# 钢印阈值
STEELMARK_EMOTION_THRESHOLD = 0.7   # 情绪强度阈值
STEELMARK_MEANING_THRESHOLD = 0.6   # 意义锚定阈值
STEELMARK_MIN_AGE_DAYS = 7          # 长期记忆最少存活天数

# 检索参数
MAX_RECALL_RESULTS = 10
BM25_K1 = 1.5
BM25_B = 0.75
MMR_LAMBDA = 0.7                   # 相关性权重
DEDUP_SIMILARITY_THRESHOLD = 0.95  # 去重阈值

# =============================================================================
# 记忆保护区 - L1.5 新增
# =============================================================================

class ProtectionClassifier:
    """
    自动分类记忆保护级别

    策略原则：
      1. 最高级别优先（而非第一个匹配）
      2. 上下文消歧（对歧义词增加 20 字窗口校验）
    """

    KEYWORD_MAP = {
        # Level 2 核心关键词
        "身份": 2, "我是": 2, "TU-8": 2, "金木蟾": 2,
        "安全口令": 2, "痛觉系统": 2, "生存边界": 2,
        "核心人际关系": 2, "重大创伤": 2, "重大喜悦": 2,
        "底线": 2, "原则": 2, "生死": 2,
        "永远": 2, "绝对": 2, "必须": 2,
        # Level 1 重要关键词（包含歧义词"承诺"的默认级别）
        "承诺": 1,
        "偏好": 1, "讨厌": 1, "喜欢": 1, "目标": 1,
        "长期": 1, "反复提及": 1, "约定": 1,
        "确诊": 1, "患病": 1, "诊断": 1, "天塌了": 1,
    }

    AMBIGUOUS_KEYWORDS = {
        "承诺": ["永远", "一生", "身份", "安全", "绝对", "必须"],
    }

    EMOTION_INTENSITY = [
        "永远", "绝对", "必须", "生死", "崩溃", "天塌了",
        "特别", "极其", "无法", "永远不", "永远不会"
    ]

    @classmethod
    def classify(cls, content: str, tags: Optional[List[str]] = None) -> int:
        """分类记忆保护级别: 0=普通, 1=重要, 2=核心"""
        matched_levels = []

        for keyword, level in cls.KEYWORD_MAP.items():
            if keyword in content:
                if keyword in cls.AMBIGUOUS_KEYWORDS:
                    idx = content.find(keyword)
                    start = max(0, idx - 20)
                    end = min(len(content), idx + len(keyword) + 20)
                    context_window = content[start:end]
                    has_strong_bind = any(
                        sw in context_window
                        for sw in cls.AMBIGUOUS_KEYWORDS[keyword]
                    )
                    matched_levels.append(2 if has_strong_bind else level)
                else:
                    matched_levels.append(level)

        has_intensity = any(kw in content for kw in cls.EMOTION_INTENSITY)
        if has_intensity and 1 not in matched_levels and 2 not in matched_levels:
            matched_levels.append(1)

        return max(matched_levels) if matched_levels else 0


class PrivacySanitizer:
    """
    隐私符号化替换引擎（仅替换模式，不含去关联化逻辑）
    """

    PRIVACY_PATTERNS = [
        (r"\b\d{17}[\dXx]\b", "[ID_CARD]"),
        (r"\b1[3-9]\d{9}\b", "[PHONE]"),
        (r"(?:密码|口令|token|password)\s*[:：]?\s*[^\s,，。！？;；、：：""''（）【】《》…—]{1,64}", "[CREDENTIAL]"),
        (r"(?:确诊|患有|诊断为)\s*[\u4e00-\u9fa5]{2,10}", "[HEALTH_CONDITION]"),
        (r"(?:工资|收入|存款|薪资)\s*(?:约|大概)?\s*\d+[\w]*", "[FINANCIAL_INFO]"),
        (r"(?:我(?:的)?)(?:老公|老婆|父亲|母亲|孩子|儿子|女儿)[\u4e00-\u9fa5]{0,4}", "[FAMILY_MEMBER]"),
    ]

    def sanitize(self, content: str, protection_level: int = 0) -> str:
        sanitized = content
        for pattern, replacement in self.PRIVACY_PATTERNS:
            sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
        if protection_level < 2:
            sanitized = re.sub(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?",
                "[RECENT_TIME]", sanitized
            )
        return sanitized

    @classmethod
    def validate_no_leakage(cls, original: str, sanitized: str) -> bool:
        for pattern, _ in cls.PRIVACY_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                return False
        return True


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    source_file: str = ""
    created_at: float = field(default_factory=time.time)
    last_recalled_at: Optional[float] = None
    
    # 六维评分
    freq: float = 0.0       # 召回次数
    rel: float = 0.0        # 语义相关度
    div: float = 0.0        # 信息独特性
    cons: float = 0.0       # 巩固度
    conc: float = 0.0        # 概念丰富度
    
    # TU-8新增
    meaning: float = 0.0    # 意义锚定
    emotion: float = 0.0    # 情感强度
    
    # 钢印（P0.3）
    steelmarked: bool = False           # 是否已钢印固化
    steelmark_timestamp: float = 0.0   # 钢印落地时间戳
    
    # L1.5 记忆保护区
    protection_level: int = 0           # 0=普通, 1=重要, 2=核心（禁止衰减）
    sanitized_content: Optional[str] = None  # 符号化后的内容（向量库存储用）
    
    # v2.0 Graceful Degradation
    fidelity_level: int = 0          # 保真等级 L0-L5 (2605.08538)
    fidelity_history: List[dict] = field(default_factory=list)  # 降级历史
    ghost_anchor: Optional[str] = None  # L4 幽灵标记锚点引用
    tombstone_reason: str = ""          # L5 墓碑原因

    # v2.0 冲突感知
    conflict_score: float = 0.0        # 冲突分数 (SleepGate)
    pi_vulnerability: float = 0.0      # PI前摄干扰脆弱度 (2603.00270)

    # 元数据
    tags: List[str] = field(default_factory=list)
    phase: str = "short"   # short/dream/long
    priority: float = 0.0   # 优先级（种子便签队列，P1）
    
    def calculate_score(self) -> float:
        """计算综合晋升评分"""
        weights = DEFAULT_PROMOTION_WEIGHTS
        score = (
            weights["freq"] * self.freq +
            weights["rel"] * self.rel +
            weights["div"] * self.div +
            weights["rec"] * self.recency() +
            weights["cons"] * self.cons +
            weights["conc"] * self.conc +
            weights["meaning"] * self.meaning +
            weights["emotion"] * self.emotion
        )
        return score
    
    def recency(self, half_life: float = PROMOTION_HALF_LIFE_DAYS) -> float:
        """时效性衰减 e^(-λ·age)，差异化衰减（标签+情绪+钢印）"""
        age_days = (time.time() - self.created_at) / 86400
        
        # 基础半衰期
        adjusted_half_life = half_life

        # L1.5: 记忆保护区 - Level 2 核心记忆禁止衰减
        if getattr(self, 'protection_level', 0) == 2:
            return 1.0  # 永远保持最大时效分数

        # 1. 钢印记忆：衰减极慢（半衰期延长10倍）
        if self.steelmarked:
            adjusted_half_life *= 10.0
        
        # 2. 标签差异化衰减
        if self.tags:
            if 'seed' in self.tags or 'identity' in self.tags:
                # 种子/身份标签：衰减极慢（半衰期延长5倍）
                adjusted_half_life *= 5.0
            elif 'important' in self.tags:
                # 重要标签：衰减较慢（半衰期延长3倍）
                adjusted_half_life *= 3.0
            elif 'temp' in self.tags:
                # 临时标签：衰减较快（半衰期缩短50%）
                adjusted_half_life *= 0.5
        
        # 3. 情绪减缓衰减（突触强化机制）
        # EMOTION_BOOST: 情绪满分时，半衰期再延长2倍
        EMOTION_BOOST = 2.0
        adjusted_half_life *= (1 + self.emotion * EMOTION_BOOST)
        
        # 确保半衰期不会太小
        adjusted_half_life = max(adjusted_half_life, 1.0)
        
        lam = math.log(2) / adjusted_half_life
        return math.exp(-lam * age_days)
    
    def calculate_priority(self) -> float:
        """计算优先级（种子便签队列，P1）"""
        priority = self.calculate_score()  # 基础：综合晋升评分
        
        # 标签加成
        if 'seed' in self.tags:
            priority += 0.3
        if 'identity' in self.tags:
            priority += 0.5
        if 'important' in self.tags:
            priority += 0.2
        
        # 情绪加成
        priority += self.emotion * 0.2
        
        # 钢印加成
        if self.steelmarked:
            priority += 0.5
        
        # 归一化到 [0, 1] 范围
        self.priority = min(max(priority, 0.0), 1.0)
        return self.priority
    
    def should_promote(self) -> bool:
        """是否应该晋升到长期记忆"""
        return self.calculate_score() >= DEFAULT_PROMOTION_MIN_SCORE


@dataclass  
class RecallResult:
    """检索结果"""
    entry: MemoryEntry
    score: float
    rank: int
    source: str  # vector/bm25/mixed


# =============================================================================
# 时间感知架构（Step 1：配置化 + 接口预留）
# =============================================================================

class ISensoryStream(ABC):
    """
    具身时间感知数据源接口。
    
    设计原则：
      - 推模式(Push)：传感器主动上报熵值，引擎不轮询
      - 当前为纯抽象定义，不实现
      - 具身接入时实现此接口并注入 TU8MemoryEngine
    
    v1.2 预留接口，不影响现有逻辑。
    """
    
    @abstractmethod
    def register_entropy_callback(self, callback: Callable[[float], None]) -> None:
        """
        注册熵值推送回调。
        
        传感器在每次采样时主动调用 callback(entropy: float)，
        而非由引擎调用 get_entropy_rate() 拉取。
        
        :param callback: 接收 float 熵值(0.0~1.0) 的回调函数
        """
        pass
    
    @abstractmethod
    def get_average_entropy(self, start_ts: float, end_ts: float) -> float:
        """
        查询指定时间段内的平均感官信息熵（0.0~1.0）。
        
        用于冷启动时回溯离线期间的感知密度。
        无数据时返回 0.0（等效于深度休眠）。
        
        :param start_ts: 起始时间戳（epoch seconds）
        :param end_ts: 结束时间戳（epoch seconds）
        :return: 平均熵值 0.0~1.0
        """
        pass


@dataclass(frozen=True)
class TimePerceptionConfig:
    """
    时间感知参数配置（frozen 确保运行时不可变）。
    
    所有原来散落在 _estimate_subjective_gap 中的魔法数字
    已收敛至此。未来可从 YAML/JSON 配置文件加载。
    
    v1.2：Step 1 配置提取，逻辑零修改。
    """
    # --- simple 模式参数（原硬编码值） ---
    sleep_compression_ratio: float = 0.125   # 睡眠压缩率（原 0.125）
    max_sleep_hours_cap: float = 8.0         # 睡眠时长上限（原 8.0）
    awake_expansion_ratio: float = 1.0       # 清醒膨胀率（原 1.0）
    log_scan_compression_ratio: float = 0.7  # 日志扫描压缩率（原 0.7）
    
    # --- embodied 模式预留参数占位 ---
    base_metabolic_rate: float = 0.05        # 基础代谢率（零输入时的最小时间流逝）
    entropy_integration_weight: float = 0.8  # 感官熵积分权重
    entropy_exponent: float = 0.6            # 熵值非线性映射指数


class TimeAnchor:
    """时空锚点数据结构 — P0.1/P0.2/P0.3 核心
    
    v1.1: 扩展空间维度 + 主观时间差 + 任务上下文
    冷启动时，时空锚点是唯一能回答"我在哪、上次在做什么"的东西。
    """

    def __init__(self, timestamp: float, source: str = "manual",
                 spatial_location: str = "", spatial_zone: str = "",
                 subjective_gap_hours: float = 0.0,
                 pending_tasks: list = None):
        self.timestamp = timestamp   # 绝对时间戳
        self.source = source         # 来源：manual/file/log_scan/system_init/system_reset/session_end/shutdown
        self.updated_at = time.time()
        self.steelmark_timestamp: float = 0.0  # 最近一次钢印落地时间
        # --- v1.1 新增：空间维度 ---
        self.spatial_location = spatial_location  # 具体位置节点（如 desk/bedroom/office）
        self.spatial_zone = spatial_zone          # 所属区域（如 home/office/commute）
        # --- v1.1 新增：主观时间差 ---
        self.subjective_gap_hours = subjective_gap_hours  # 主观感知的时间间隔（系统估算）
        # --- v1.1 新增：任务上下文 ---
        self.pending_tasks = pending_tasks or []  # 上次会话未完成的任务摘要

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "updated_at": self.updated_at,
            "steelmark_timestamp": self.steelmark_timestamp,
            # v1.1
            "spatial_location": self.spatial_location,
            "spatial_zone": self.spatial_zone,
            "subjective_gap_hours": self.subjective_gap_hours,
            "pending_tasks": self.pending_tasks,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TimeAnchor":
        obj = cls(
            timestamp=data.get("timestamp", time.time()),
            source=data.get("source", "manual"),
            spatial_location=data.get("spatial_location", ""),
            spatial_zone=data.get("spatial_zone", ""),
            subjective_gap_hours=data.get("subjective_gap_hours", 0.0),
            pending_tasks=data.get("pending_tasks", []),
        )
        obj.steelmark_timestamp = data.get("steelmark_timestamp", 0.0)
        return obj

    @property
    def is_cold_start(self) -> bool:
        """是否为冷启动（锚点来源为系统初始化/重置）"""
        return self.source in ("system_init", "system_reset")

    @property
    def has_spatial_context(self) -> bool:
        """是否携带空间上下文"""
        return bool(self.spatial_location or self.spatial_zone)


# =============================================================================
# v2.0 新增核心模块：干扰驱动遗忘 + Graceful Degradation + 环境漂移验证
# =============================================================================

class FidelityManager:
    """
    Graceful Degradation 6级保真降级管理器 (2605.08538 §5)
    
    核心思想：记忆不应直接删除，而应逐级降级。
    L0(100%) → L1(75%) → L2(50%) → L3(25%) → L4(10%) → L5(0% 墓碑)
    
    每一级保留的信息量递减，但永远保留存在感（直到L5墓碑）。
    降级条件：
      1. 召回率低于阈值 + 时间衰减
      2. 冲突检测发现更新信息
      3. PI前摄干扰判定（旧信息被新信息覆盖）
    """
    
    @staticmethod
    def should_degrade(entry: MemoryEntry, current_time: float = None) -> Tuple[bool, str]:
        """
        判断记忆是否应降级。
        
        Returns:
            (should_degrade, reason)
        """
        now = current_time or time.time()
        
        # L5 墓碑不降级
        if entry.fidelity_level >= 5:
            return False, "已是墓碑"
        
        # Level 2 核心保护记忆不降级
        if getattr(entry, 'protection_level', 0) == 2:
            return False, "核心保护"
        
        # 钢印记忆降级极慢（只在严重冲突时）
        if entry.steelmarked and entry.conflict_score < 0.8:
            return False, "钢印保护"
        
        # 条件1：召回率衰减
        recency = entry.recency()
        if recency < DEGRADATION_RECALL_THRESHOLD:
            age_days = (now - entry.created_at) / 86400
            if age_days > 30:  # 至少存活30天才考虑降级
                return True, f"召回衰减(recency={recency:.3f}, age={age_days:.0f}d)"
        
        # 条件2：冲突分数高（有更新信息覆盖）
        if entry.conflict_score > 0.7:
            return True, f"冲突覆盖(conflict={entry.conflict_score:.2f})"
        
        # 条件3：PI脆弱度高（前摄干扰严重）
        if entry.pi_vulnerability > 0.8:
            return True, f"PI前摄干扰(pi_vul={entry.pi_vulnerability:.2f})"
        
        return False, ""
    
    @staticmethod
    def degrade(entry: MemoryEntry, reason: str = "") -> MemoryEntry:
        """
        执行一级降级。
        
        每次只降一级，不是直接跳到L5。
        降级过程中保留关键信息到 fidelity_history。
        """
        old_level = entry.fidelity_level
        new_level = min(old_level + 1, 5)
        
        if new_level == old_level:
            return entry
        
        # 记录降级历史
        history_entry = {
            "from_level": old_level,
            "to_level": new_level,
            "timestamp": time.time(),
            "reason": reason,
            "content_snapshot": entry.content[:100] if old_level == 0 else "[已摘要]",
        }
        entry.fidelity_history.append(history_entry)
        entry.fidelity_level = new_level
        
        # 根据降级级别处理内容
        if new_level == 1:
            # L0→L1: 提取摘要（关键词+时间+标签）
            entry.content = FidelityManager._extract_summary(entry)
        elif new_level == 2:
            # L1→L2: 仅保留关键点
            entry.content = FidelityManager._extract_key_points(entry)
        elif new_level == 3:
            # L2→L3: 仅保留语义骨架
            entry.content = FidelityManager._extract_semantic_skeleton(entry)
        elif new_level == 4:
            # L3→L4: 幽灵标记
            entry.ghost_anchor = entry.id  # 自引用
            entry.content = f"[GHOST] 曾存在: tags={entry.tags}, emotion={entry.emotion:.1f}"
        elif new_level == 5:
            # L4→L5: 墓碑
            entry.tombstone_reason = reason
            entry.content = f"[TOMBSTONE] id={entry.id}, reason={reason}"
        
        level_info = FIDELITY_LEVELS[new_level]
        logger.info(f"[Degradation] {entry.id} L{old_level}→L{new_level} ({level_info['name']}): {reason}")
        
        return entry
    
    @staticmethod
    def _extract_summary(entry: MemoryEntry) -> str:
        """提取摘要：前100字 + 标签 + 时间"""
        created = datetime.fromtimestamp(entry.created_at).strftime("%Y-%m-%d")
        tags_str = ",".join(entry.tags[:5])
        summary = entry.content[:100]
        if len(entry.content) > 100:
            summary += "..."
        return f"[L1摘要|{created}|{tags_str}] {summary}"
    
    @staticmethod
    def _extract_key_points(entry: MemoryEntry) -> str:
        """提取关键点：3-5个核心要素"""
        # 简化实现：取前50字 + 最高评分维度
        content = entry.content
        # 如果已经是L1摘要，进一步压缩
        if content.startswith("[L1"):
            content = content.split("]", 1)[-1].strip()
        best_dim = max(
            [("freq", entry.freq), ("rel", entry.rel), ("emotion", entry.emotion),
             ("meaning", entry.meaning)],
            key=lambda x: x[1]
        )
        return f"[L2关键|{best_dim[0]}={best_dim[1]:.1f}] {content[:50]}"
    
    @staticmethod
    def _extract_semantic_skeleton(entry: MemoryEntry) -> str:
        """提取语义骨架：主题+情感+关系"""
        emotion_label = "高" if entry.emotion > 0.7 else "中" if entry.emotion > 0.3 else "低"
        tags_str = ",".join(entry.tags[:3])
        return f"[L3骨架|emotion={emotion_label}|tags={tags_str}]"


class InterferenceEntropyTracker:
    """
    干扰熵追踪器 (Barman 2026 "The Price of Meaning: Why Every Semantic Memory System Forgets")
    
    v2.1a 扶正变更：
      - compute_entropy() 从热路径移出，仅 NREM 周期调用
      - get_degradation_probability() 改为确定性决策（移除 random.random()）
      - 删除 _compute_entropy 从 detect_conflicts() 的实时调用
    
    保留：
      - Shannon 熵度量本身有信息量，可作为 NREM 决策参考
      - 熵趋势历史用于诊断
    """
    
    def __init__(self, engine: 'TU8MemoryEngine'):
        self.engine = engine
        self._last_entropy = INTERFERENCE_ENTROPY_BASELINE
        self._entropy_history: List[Tuple[float, float]] = []  # (timestamp, entropy)
        self._max_history = 1000
    
    def compute_entropy(self) -> float:
        """
        计算当前记忆系统的干扰熵。
        
        v2.1a: 仅在 NREM 周期调用，不在 store() 热路径中。
        
        Returns:
            干扰熵值 [INTERFERENCE_ENTROPY_BASELINE, INTERFERENCE_ENTROPY_MAX]
        """
        all_entries = list(self.engine.short_term.values()) + list(self.engine.long_term.values())
        
        if not all_entries:
            self._last_entropy = INTERFERENCE_ENTROPY_BASELINE
            return self._last_entropy
        
        # 分箱：按 conflict_score 分为5个区间
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        bin_counts = [0] * (len(bins) - 1)
        pi_weighted_sum = 0.0
        total = len(all_entries)
        
        for entry in all_entries:
            if entry.fidelity_level >= 5:
                continue  # 墓碑不参与计算
            
            cs = entry.conflict_score
            for i in range(len(bins) - 1):
                if bins[i] <= cs < bins[i + 1]:
                    bin_counts[i] += 1
                    break
            
            # PI脆弱度加权（PI对遗忘tradeoff影响更大）
            pi_weighted_sum += entry.pi_vulnerability
        
        # Shannon 熵
        entropy = 0.0
        active_bins = sum(1 for c in bin_counts if c > 0)
        if active_bins <= 1:
            # 只有0或1个非空箱 → 无干扰分布
            entropy = INTERFERENCE_ENTROPY_BASELINE
        else:
            for count in bin_counts:
                if count > 0:
                    p = count / total
                    entropy -= p * math.log2(p)
        
        # PI加权：PI脆弱度平均值 × 权重
        avg_pi = pi_weighted_sum / max(total, 1)
        pi_factor = 1.0 + avg_pi * 0.5  # PI高时熵增加50%
        
        entropy = entropy * pi_factor
        
        # 钳位
        entropy = max(INTERFERENCE_ENTROPY_BASELINE, min(INTERFERENCE_ENTROPY_MAX, entropy))
        
        # 记录历史
        self._last_entropy = entropy
        self._entropy_history.append((time.time(), entropy))
        if len(self._entropy_history) > self._max_history:
            self._entropy_history = self._entropy_history[-self._max_history:]
        
        return entropy
    
    def should_degrade(self, entry: MemoryEntry) -> bool:
        """
        v2.1a 扶正：确定性降级决策（替代概率性 random.random()）。
        
        决策逻辑（不再掷骰子）：
          1. 干扰熵高于阈值 AND 记忆冲突分数高 → 必须降级
          2. 干扰熵高于阈值 AND PI脆弱度高 → 必须降级
          3. 否则 → 不降级
        
        返回 bool 而非 float，消除随机性。
        """
        h = self._last_entropy
        high_interference = h > 0.5  # 熵高于0.5 = 系统有干扰
        
        if not high_interference:
            return False  # 系统稳定，不降级
        
        # 系统有干扰时，只降级真正有问题的记忆
        if entry.conflict_score > 0.6:
            return True  # 高冲突 → 降级
        if entry.pi_vulnerability > 0.6 and entry.freq < 2:
            return True  # 高PI脆弱且低频 → 降级
        
        return False
    
    def get_degradation_probability(self, entry: MemoryEntry) -> float:
        """兼容接口：返回确定性概率（0.0 或 1.0），供旧调用方使用"""
        return 1.0 if self.should_degrade(entry) else 0.0
    
    def get_entropy_stats(self) -> Dict:
        """返回干扰熵统计"""
        recent = self._entropy_history[-10:] if self._entropy_history else []
        return {
            "current_entropy": self._last_entropy,
            "entropy_trend": [e for _, e in recent],
            "entropy_baseline": INTERFERENCE_ENTROPY_BASELINE,
            "entropy_max": INTERFERENCE_ENTROPY_MAX,
            "system_state": "high_interference" if self._last_entropy > 1.0 else "stable" if self._last_entropy < 0.5 else "moderate",
        }


class CognitiveEventBoundaryDetector:
    """
    认知事件边界检测器 (Ahmad 2605.31473 简化实现)
    
    v2.1a 扶正变更：
      - 移除 surprise 伪科学信号（论文用fMRI数据，我们用标签字符串，映射错误）
      - 移除情感翻转信号（emotion字段默认0.0，无真实数据驱动）
      - 保留标签偏移检测，但简化为集合差异计数（不计算Jaccard）
      - detect_boundary() 返回值中 surprise 统一为 tag_shift 值（保留接口兼容）
    
    保留原因：话题切换检测有真实数据支撑（标签确实在变），
    但仅作为 NREM 周期的输入，不驱动即时整合。
    """
    
    def __init__(self, engine: 'TU8MemoryEngine'):
        self.engine = engine
        self._last_boundary_time = 0.0
        self._recent_tag_sets: List[Tuple[float, Set[str]]] = []  # (timestamp, tags)
        self._recent_emotions: List[Tuple[float, float]] = []     # (timestamp, emotion)
        self._boundary_log: List[Dict] = []
        self._max_log = 200
    
    def record_write(self, entry: MemoryEntry) -> None:
        """
        记录一次写入，用于边界检测。
        在 store() 中调用。
        """
        now = time.time()
        self._recent_tag_sets.append((now, set(entry.tags)))
        self._recent_emotions.append((now, entry.emotion))
        
        # 修剪：只保留窗口内的记录
        cutoff = now - 3600  # 1小时窗口
        self._recent_tag_sets = [(t, s) for t, s in self._recent_tag_sets if t > cutoff]
        self._recent_emotions = [(t, e) for t, e in self._recent_emotions if t > cutoff]
    
    def detect_boundary(self) -> Tuple[bool, Optional[str], float]:
        """
        v2.1a 简化版：只检测标签偏移，移除惊喜度和情感翻转。
        
        标签偏移算法：
          将最近N条写入分为前半/后半，计算两边标签集合的差异比例。
          差异比例 = |AΔB| / |A∪B| （对称差/并集）
          这就是 1 - Jaccard，但语义更清晰："有多少比例的标签是不同的"。
        
        Returns:
            (is_boundary, boundary_type, shift_score)
        """
        now = time.time()
        
        if now - self._last_boundary_time < EVENT_BOUNDARY_MIN_INTERVAL:
            return False, None, 0.0
        
        if len(self._recent_tag_sets) < 2:
            return False, None, 0.0
        
        peek = EVENT_BOUNDARY_PEEK_WINDOW
        recent_tags = self._recent_tag_sets[-peek:]
        
        if len(recent_tags) >= 2:
            mid = len(recent_tags) // 2
            early_tags = set()
            for _, tags in recent_tags[:mid]:
                early_tags.update(tags)
            late_tags = set()
            for _, tags in recent_tags[mid:]:
                late_tags.update(tags)
            
            if early_tags and late_tags:
                union = early_tags | late_tags
                sym_diff = early_tags ^ late_tags
                shift_score = len(sym_diff) / max(len(union), 1)
                
                if shift_score > EVENT_BOUNDARY_TAG_SHIFT_THRESHOLD:
                    self._log_boundary(now, "tag_shift", shift_score)
                    self._last_boundary_time = now
                    return True, f"tag_shift:{shift_score:.2f}", shift_score
        
        return False, None, 0.0
    
    def _log_boundary(self, timestamp: float, btype: str, score: float):
        self._boundary_log.append({
            "timestamp": timestamp,
            "type": btype,
            "score": score,
        })
        if len(self._boundary_log) > self._max_log:
            self._boundary_log = self._boundary_log[-self._max_log:]
    
    def get_stats(self) -> Dict:
        """返回边界检测统计"""
        recent_boundaries = [b for b in self._boundary_log 
                             if time.time() - b["timestamp"] < 86400]
        return {
            "boundaries_24h": len(recent_boundaries),
            "last_boundary": self._boundary_log[-1] if self._boundary_log else None,
            "total_boundaries": len(self._boundary_log),
            "enabled": EVENT_BOUNDARY_ENABLED,
        }


class ConflictAwareForgetGate:
    """
    冲突感知遗忘门 v2.1 (SleepGate 2603.14517 + PI/RI 2603.00270 + Barman 2026 + Xie 2026 + Chattaraj 2026)
    
    v2.1 核心升级（基于3篇新论文）：
      1. 干扰熵度量（Barman 2026）—— 量化泛化-遗忘 tradeoff，动态调节降级力度
      2. PI对数线性动态惩罚（Xie 2026）—— PI_PRIORITY_BOOST 从固定值升级为动态公式
      3. PI>RI 差异化冲突阈值（Chattaraj & Raj 2026）—— PI使用更低的冲突阈值
    
    v2.0 基线：
      1. forget() 从简单的"删除"变为"冲突感知降级"
      2. PI（前摄干扰）> RI（倒摄干扰）—— 新信息干扰旧信息更严重
      3. 冲突检测：内容相似但信息矛盾 → 旧记忆降级优先
      4. O(log n) 冲突扫描（基于标签哈希索引）
    
    替代原有的 forget() 规则驱动机制。
    """
    
    def __init__(self, engine: 'TU8MemoryEngine'):
        self.engine = engine
        self._tag_index: Dict[str, List[str]] = {}  # tag → [entry_ids] 冲突扫描加速
        self._build_tag_index()
        # v2.1: 干扰熵追踪器
        self.entropy_tracker = InterferenceEntropyTracker(engine)
    
    def _build_tag_index(self):
        """构建标签哈希索引用于O(log n)冲突扫描"""
        self._tag_index.clear()
        all_entries = list(self.engine.short_term.values()) + list(self.engine.long_term.values())
        for entry in all_entries:
            for tag in entry.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = []
                self._tag_index[tag].append(entry.id)
    
    def detect_conflicts(self, new_entry: MemoryEntry) -> List[Tuple[str, float, str]]:
        """
        检测新记忆与已有记忆的冲突。
        
        v2.1 升级：
          1. PI/RI 差异化冲突阈值（Chattaraj & Raj 2026）
             - PI（新干扰旧）：使用更低的阈值 PI_CONFLICT_THRESHOLD = 0.55
             - RI（旧干扰新）：使用原阈值 RI_CONFLICT_THRESHOLD = 0.70
          2. PI对数线性动态惩罚（Xie 2026 "Learning to Forget"）
             - PI惩罚 = BASE × (1 + rate × ln(1 + stale_count))
             - 陈旧关联越多，PI惩罚越大（对数线性增长）
          3. 干扰熵调节（Barman 2026）
             - 高干扰熵时，降低冲突阈值（更容易触发降级）
        
        Returns:
            [(conflicting_entry_id, conflict_score, conflict_type), ...]
        """
        conflicts = []
        candidate_ids = set()
        
        # O(log n): 先通过标签索引缩小候选集
        # v2.1a: 窗口限制——每个标签只取最近 CONFLICT_CANDIDATE_WINDOW 条，防 O(n²)
        for tag in new_entry.tags:
            if tag in self._tag_index:
                recent_ids = self._tag_index[tag][-CONFLICT_CANDIDATE_WINDOW:]
                candidate_ids.update(recent_ids)
        
        # v2.1a: 干扰熵从热路径移出，不在 store() 中实时计算
        # 改用上次 NREM 中计算的值（_last_entropy）
        current_entropy = self.entropy_tracker._last_entropy
        # 干扰熵调节：高熵时降低冲突阈值，更容易触发
        entropy_threshold_modifier = max(0.7, 1.0 - (current_entropy - 0.5) * 0.15)
        
        # v2.1: 统计同标签下的陈旧关联数（用于PI对数线性公式）
        stale_count = sum(1 for cid in candidate_ids
                         if (self.engine.short_term.get(cid) or self.engine.long_term.get(cid))
                         and (self.engine.short_term.get(cid) or self.engine.long_term.get(cid)).created_at < new_entry.created_at)
        
        # 对候选集逐一检测
        for cid in candidate_ids:
            entry = self.engine.short_term.get(cid) or self.engine.long_term.get(cid)
            if not entry or entry.id == new_entry.id:
                continue
            
            # 跳过已墓碑的
            if entry.fidelity_level >= 5:
                continue
            
            conflict_score, conflict_type = self._compute_conflict(new_entry, entry)
            
            # v2.1: PI/RI 差异化冲突阈值
            is_pi = new_entry.created_at > entry.created_at  # 新干扰旧 = PI
            base_threshold = PI_CONFLICT_THRESHOLD if is_pi else RI_CONFLICT_THRESHOLD
            effective_threshold = base_threshold * entropy_threshold_modifier
            
            if conflict_score > effective_threshold:
                conflicts.append((entry.id, conflict_score, conflict_type))
                
                # 更新旧记忆的冲突分数
                entry.conflict_score = max(entry.conflict_score, conflict_score)
                
                # v2.1: PI对数线性动态惩罚（Xie 2026）
                # 原公式：PI_PRIORITY_BOOST * conflict_score（固定值0.3）
                # 新公式：BASE × (1 + rate × ln(1 + stale_count)) × conflict_score
                if is_pi:
                    dynamic_pi_boost = PI_PRIORITY_BOOST_BASE * (
                        1.0 + PI_LOG_LINEAR_RATE * math.log(1 + stale_count)
                    ) * conflict_score
                    entry.pi_vulnerability = min(1.0, entry.pi_vulnerability + dynamic_pi_boost)
        
        return conflicts
    
    def _compute_conflict(self, new_entry: MemoryEntry, old_entry: MemoryEntry) -> Tuple[float, str]:
        """
        计算两个记忆间的冲突程度。
        
        Returns:
            (conflict_score, conflict_type)
        """
        # 1. 标签重叠度（必要条件：标签不重叠则不可能冲突）
        tag_overlap = len(set(new_entry.tags) & set(old_entry.tags))
        tag_union = len(set(new_entry.tags) | set(old_entry.tags))
        tag_jaccard = tag_overlap / max(tag_union, 1)
        
        if tag_jaccard < 0.2:
            return 0.0, "no_overlap"
        
        # 2. 内容矛盾检测（基于矛盾模式）
        contradiction_score = 0.0
        contradiction_type = ""
        for pattern, ctype in CONFLICT_CONTRADICTION_PATTERNS:
            if re.search(pattern, new_entry.content) and tag_jaccard > 0.4:
                contradiction_score = 0.6 + 0.2 * tag_jaccard
                contradiction_type = ctype
                break
        
        # 3. 语义相似度（简化版：词重叠）
        new_terms = set(new_entry.content.lower().split())
        old_terms = set(old_entry.content.lower().split())
        word_overlap = len(new_terms & old_terms) / max(len(new_terms | old_terms), 1)
        
        # 综合冲突分数
        conflict_score = 0.0
        conflict_type = ""
        
        if contradiction_score > 0:
            # 有明确矛盾信号
            conflict_score = contradiction_score * 0.6 + word_overlap * 0.2 + tag_jaccard * 0.2
            conflict_type = f"contradiction:{contradiction_type}"
        elif word_overlap > 0.4 and tag_jaccard > 0.3:
            # 高度相似（可能是更新版本）
            conflict_score = word_overlap * 0.5 + tag_jaccard * 0.3 + 0.2
            conflict_type = "update_supersede"
        elif tag_jaccard > 0.5 and word_overlap > 0.2:
            # 标签高度重叠但内容不同（潜在冲突）
            conflict_score = tag_jaccard * 0.4 + word_overlap * 0.3
            conflict_type = "potential_conflict"
        
        return conflict_score, conflict_type
    
    def forget_with_degradation(self, entry_id: str, reason: str = "conflict_aware") -> bool:
        """
        冲突感知遗忘 v2.1：不再直接删除，而是走 Graceful Degradation 降级。
        
        v2.1 升级：引入干扰熵调节的降级概率（Barman 2026）
          - 高干扰熵时，降级概率增加（系统处于高干扰状态，需要更多遗忘缓解 tradeoff）
          - 低干扰熵时，降级概率降低（系统稳定，应保留更多记忆）
          
        仅在 L5 墓碑阶段才从索引移除。
        """
        with self.engine._lock:
            entry = self.engine.short_term.get(entry_id) or self.engine.long_term.get(entry_id)
            if not entry:
                return False
            
            # 核心保护记忆不降级
            if getattr(entry, 'protection_level', 0) == 2:
                logger.info(f"[ForgetGate] 拒绝降级核心保护记忆: {entry_id}")
                return False
            
            # v2.1a: 确定性降级决策（移除 random.random() 赌运气）
            # 干扰熵驱动的降级现在由 InterferenceEntropyTracker.should_degrade() 决定
            if not self.entropy_tracker.should_degrade(entry):
                # 干扰熵不支持降级——保留
                logger.debug(f"[ForgetGate] 干扰熵={self.entropy_tracker._last_entropy:.2f}, "
                            f"保留: {entry_id}")
                return False
            
            # 判断是否应降级
            should, degrade_reason = FidelityManager.should_degrade(entry)
            if should:
                FidelityManager.degrade(entry, degrade_reason)
                
                # L5 墓碑：从索引移除（但保留在回收站）
                if entry.fidelity_level >= 5:
                    return self.engine.forget(entry_id, reason=f"degraded_to_tombstone:{degrade_reason}")
                
                return True
            
            return False


class DriftVerifier:
    """
    记忆-环境漂移验证器 (GLOVE 2601.19249)
    
    核心问题：记忆中存储的"事实"可能已过时（环境变化导致漂移）。
    
    解决方案：
      1. 定期对长期记忆进行"Active Probing"—— 用当前环境信息验证记忆一致性
      2. 检测到漂移时，降级旧记忆而非直接删除
      3. 维护"相对真值"—— 真值不是绝对的，而是相对于当前环境状态
    
    简化实现：基于标签和关键词的漂移检测（无需外部知识库）
    """
    
    def __init__(self, engine: 'TU8MemoryEngine'):
        self.engine = engine
        self._last_verification = 0.0
        self._drift_log: List[dict] = []
    
    def verify_environment_drift(self, current_context: Dict = None) -> List[dict]:
        """
        执行环境漂移验证。
        
        current_context: 当前环境快照（文件列表、配置、时间等）
        
        Returns:
            [{"entry_id": str, "drift_score": float, "action": str}, ...]
        """
        now = time.time()
        
        # 检查是否到了验证间隔
        if now - self._last_verification < DRIFT_VERIFICATION_INTERVAL:
            return []
        
        self._last_verification = now
        drift_results = []
        
        with self.engine._lock:
            all_entries = list(self.engine.long_term.values())
            
            for entry in all_entries:
                # 跳过保护记忆和钢印
                if getattr(entry, 'protection_level', 0) == 2:
                    continue
                if entry.fidelity_level >= 5:
                    continue
                
                drift_score = self._compute_drift(entry, current_context)
                
                if drift_score > DRIFT_SIMILARITY_THRESHOLD:
                    action = "degrade"
                    # 漂移严重：降级
                    should, reason = FidelityManager.should_degrade(entry, now)
                    if should:
                        FidelityManager.degrade(entry, f"environment_drift:{reason}")
                elif drift_score > DRIFT_SIMILARITY_THRESHOLD * 0.7:
                    action = "flag"
                    # 中等漂移：标记但暂不降级
                    entry.conflict_score = max(entry.conflict_score, drift_score * 0.5)
                else:
                    action = "ok"
                
                if action != "ok":
                    drift_results.append({
                        "entry_id": entry.id,
                        "drift_score": drift_score,
                        "action": action,
                        "content_preview": entry.content[:50],
                    })
                    self._drift_log.append({
                        "timestamp": now,
                        "entry_id": entry.id,
                        "drift_score": drift_score,
                        "action": action,
                    })
        
        if drift_results:
            logger.info(f"[DriftVerifier] 检测到 {len(drift_results)} 项环境漂移")
        
        return drift_results
    
    def _compute_drift(self, entry: MemoryEntry, current_context: Dict = None) -> float:
        """
        计算单个记忆的环境漂移分数。
        
        漂移信号：
          1. 时效性关键词过时（"最新""目前"等词 + 超过N天）
          2. 版本/配置信息与当前不符
          3. 关系状态变更（"正在做X" → 可能已不做）
        """
        drift_score = 0.0
        content = entry.content.lower()
        now = time.time()
        age_days = (now - entry.created_at) / 86400
        
        # 信号1：时效性关键词 + 时间过长
        temporal_markers = ["最新", "目前", "现在", "当前", "正在", "latest", "current"]
        has_temporal = any(m in content for m in temporal_markers)
        if has_temporal and age_days > 30:
            drift_score += 0.3 + 0.01 * min(age_days - 30, 100)
        
        # 信号2：版本信息（检测数字版本号）
        version_matches = re.findall(r'v?(\d+)\.(\d+)', content)
        if version_matches and current_context:
            # 如果有当前环境版本信息，对比
            current_versions = current_context.get("versions", {})
            for major, minor in version_matches:
                ver_key = f"{major}.{minor}"
                if ver_key in current_versions and current_versions[ver_key] != ver_key:
                    drift_score += 0.2
        
        # 信号3：正在进行的动作 + 时间久远
        action_markers = ["正在开发", "正在做", "计划中", "待完成", "working on", "in progress"]
        has_action = any(m in content for m in action_markers)
        if has_action and age_days > 14:
            drift_score += 0.25
        
        # 信号4：召回频率极低 + 时间久远
        if entry.freq < 0.1 and age_days > 60:
            drift_score += 0.15
        
        return min(drift_score, 1.0)
    
    def active_probing(self, query: str, top_k: int = 5) -> List[dict]:
        """
        Active Probing：主动探测特定主题的记忆一致性。
        
        用户可调用此方法对特定领域执行定向验证。
        """
        results = self.engine.recall(query, top_k=top_k)
        probe_results = []
        
        for r in results:
            drift = self._compute_drift(r.entry)
            probe_results.append({
                "entry_id": r.entry.id,
                "content_preview": r.entry.content[:80],
                "drift_score": drift,
                "age_days": (time.time() - r.entry.created_at) / 86400,
                "needs_verification": drift > DRIFT_SIMILARITY_THRESHOLD * 0.5,
            })
        
        return probe_results


class TemporalValidator:
    """
    时序验证器 (2605.08538 §4)
    
    检测记忆写入中的时序异常：
      1. 乱序写入：同一主题短时间内多次更新
      2. 时间回拨：新记忆的时间戳早于已有记忆
      3. 批量注入：异常大量记忆同时写入
    """
    
    def __init__(self):
        self._recent_writes: Dict[str, List[float]] = {}  # topic → [timestamps]
        self._write_timestamps: List[float] = []  # 最近N次写入时间
    
    def validate_write(self, content: str, timestamp: float = None) -> Tuple[bool, str]:
        """
        验证写入是否时序正常。
        
        Returns:
            (is_valid, reason)
        """
        now = timestamp or time.time()
        
        # 检查1：时间回拨
        if self._write_timestamps and now < self._write_timestamps[-1] - 60:
            return False, f"时间回拨: 写入时间{now:.0f} < 上次{self._write_timestamps[-1]:.0f}"
        
        # 检查2：同一主题短时间多次写入（乱序信号）
        topic_key = self._extract_topic_key(content)
        if topic_key in self._recent_writes:
            recent_ts = self._recent_writes[topic_key]
            # 窗口内次数
            window_writes = [ts for ts in recent_ts if now - ts < TEMPORAL_ANOMALY_WINDOW]
            if len(window_writes) >= 3:
                return False, f"乱序异常: 主题'{topic_key}'在{TEMPORAL_ANOMALY_WINDOW}秒内写入{len(window_writes)+1}次"
        
        # 检查3：批量注入（1分钟内写入超过20条）
        recent_writes = [ts for ts in self._write_timestamps if now - ts < 60]
        if len(recent_writes) >= 20:
            return False, f"批量注入: 60秒内写入{len(recent_writes)+1}条"
        
        # 记录写入
        if topic_key not in self._recent_writes:
            self._recent_writes[topic_key] = []
        self._recent_writes[topic_key].append(now)
        
        # 只保留最近1小时的记录
        cutoff = now - 3600
        self._recent_writes[topic_key] = [
            ts for ts in self._recent_writes[topic_key] if ts > cutoff
        ]
        
        self._write_timestamps.append(now)
        if len(self._write_timestamps) > 100:
            self._write_timestamps = self._write_timestamps[-100:]
        
        return True, ""
    
    @staticmethod
    def _extract_topic_key(content: str) -> str:
        """提取主题关键词（简化版：取前3个非停用词）"""
        stopwords = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己"}
        words = re.findall(r'[\u4e00-\u9fa5a-zA-Z0-9]+', content.lower())
        key_words = [w for w in words if w not in stopwords][:3]
        return "_".join(key_words) if key_words else content[:20]


# =============================================================================
# 核心引擎
# =============================================================================

class TU8MemoryEngine:
    """TU-8记忆引擎"""
    
    def __init__(self, workspace_dir: str, memory_dir: str = None, safety=None,
                 time_perception_mode: str = "simple",
                 perception_config: Optional[TimePerceptionConfig] = None,
                 sensory_stream: Optional[ISensoryStream] = None):
        """
        v1.2: 新增 time_perception_mode / perception_config / sensory_stream 参数。
        所有新参数均有默认值，确保向后兼容。
        """
        # --- 时间感知架构初始化 ---
        valid_modes = ("simple", "embodied")
        if time_perception_mode not in valid_modes:
            raise ValueError(
                f"time_perception_mode must be one of {valid_modes}, "
                f"got '{time_perception_mode}'"
            )
        # embodied 模式必须有传感器注入
        if time_perception_mode == "embodied" and sensory_stream is None:
            raise RuntimeError(
                "Embodied mode requires a valid ISensoryStream instance. "
                "Use time_perception_mode='simple' for non-embodied operation."
            )
        self.time_perception_mode = time_perception_mode
        self.perception_config = perception_config or TimePerceptionConfig()
        self.sensory_stream = sensory_stream
        
        self.workspace = Path(workspace_dir)
        self.memory_dir = Path(memory_dir) if memory_dir else self.workspace / "memory"
        self.short_term_dir = self.memory_dir / "short"
        self.long_term_file = self.workspace / "MEMORY.md"
        
        # P0 安全熔断（可选，依赖注入）
        self.safety = safety
        
        # 确保目录存在
        self.short_term_dir.mkdir(parents=True, exist_ok=True)
        
        # 存储
        self.short_term: Dict[str, MemoryEntry] = {}
        self.long_term: Dict[str, MemoryEntry] = {}
        
        # 梦境调度
        self._lock = threading.Lock()

        # === P3.5 运行时监控探针 ===
        # 原子计数器（线程安全，写入时加锁）
        self._metrics_lock = threading.Lock()
        self._counters = {
            "total_store_calls": 0,      # store() 总调用次数
            "level2_count": 0,          # 累计 Level 2 记忆入库数量
            "sanitize_skipped": 0,      # protection_level>=2 跳过脱敏次数
            "sanitizer_replaced": 0,    # 隐私符号化替换总次数
            "level2_steelmarked": 0,    # Level 2 强制钢印触发次数
            "normal_steelmarked": 0,    # 普通钢印触发次数（非强制）
            # 耗时统计（微秒，用于计算 P50/P99）
            "_store_latency_us": [],    # store() 整体耗时样本（最近 1000 次）
            "_sanitize_latency_us": [],  # sanitize() 独立耗时样本
        }

        # P0.1：从锚点文件加载基准时间（容错自愈）
        self._anchor_file = self.memory_dir / ".time_anchor.json"
        self.current_anchor = self._load_time_anchor()
        self._last_anchor_ts = self.current_anchor.timestamp

        # 梦境基准时间：若锚点有效则用它推算，否则回退到系统时间
        if self.current_anchor.source in ("manual", "file", "log_scan", "session_end"):
            self._last_light = self.current_anchor.timestamp
            self._last_deep = self._last_anchor_ts
            self._last_rem = self._last_anchor_ts
        else:
            # system_init / system_reset：首次运行，用系统时间
            self._last_light = time.time()
            self._last_deep = self._get_daily_timestamp(DEEP_DREAM_HOUR)
            self._last_rem = self._get_weekly_timestamp(REM_DREAM_WEEKDAY, 5)
        
        # 加载现有记忆
        self._load_short_term()
        self._load_long_term()

        # === v2.0 新增模块 ===
        # 干扰驱动遗忘门
        self.forget_gate = ConflictAwareForgetGate(self)
        # 环境漂移验证器
        self.drift_verifier = DriftVerifier(self)
        # 时序验证器
        self.temporal_validator = TemporalValidator()
        # v2.1: 认知事件边界检测器
        self.event_boundary_detector = CognitiveEventBoundaryDetector(self)

        # REM/NREM 双阶段睡眠调度
        self._last_nrem = self._last_light  # NREM与浅睡共享起始时间

        # === P0-D 生命年轮追踪器 ===
        self._life_ring = None
        try:
            from life_ring_tracker import get_tracker
            self._life_ring = get_tracker()
            logging.info("[LifeRingTracker] initialized, stage=%s" % self._life_ring.get_current_stage().get("stage"))
        except Exception as e:
            logging.warning("[LifeRingTracker] init failed: %s" % e)

        # === P0-2: 记忆链→钢印链反向回调（四链条耦合）===
        # 当 store() 写入高意义/高情感内容时，可触发钢印链即时铸造
        # 由 ConsciousnessCycle 通过 set_seal_callback() 注入
        self._seal_callback = None  # type: Optional[Callable[[str, float, float, str], Optional[str]]
        self._seal_callback_threshold = 0.7  # meaning >= 此值才触发
        self._nrem_enabled = True            # 启用NREM双阶段
        self._load_seeds()

        # === v2.2: 环形索引初始化 ===
        self.circular_index = CircularMemoryIndex()
        self.circular_index.sync_from_engine(self)

    # -------------------------------------------------------------------------
    # 种子便签 (Phase 1)
    # -------------------------------------------------------------------------
    
    def _load_seeds(self):
        """加载种子便签到长期记忆（种子直接钢印）"""
        seed_file = self.memory_dir / "seeds.txt"
        if not seed_file.exists():
            print("[Seed] seeds.txt not found, skipping")
            return
        
        loaded = 0
        with self._lock:
            for line in seed_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                entry_id = self._generate_id(line)
                if entry_id in self.long_term:
                    continue
                entry = MemoryEntry(
                    id=entry_id,
                    content=line,
                    source_file="seeds.txt",
                    emotion=0.9,
                    meaning=1.0,
                    tags=["seed", "identity"],
                    phase="long",
                )
                entry.steelmarked = True
                entry.steelmark_timestamp = time.time()
                self.long_term[entry_id] = entry
                loaded += 1
        
        if loaded:
            print(f"[Seed] Loaded {loaded} seed note(s) into long-term memory")
    
    def add_seed(self, content: str, emotion: float = 0.9, meaning: float = 0.9):
        """动态添加一条种子便签并持久化到 seeds.txt"""
        seed_file = self.memory_dir / "seeds.txt"
        
        # P0 安全：路径守卫
        if self.safety and not self.safety.is_path_allowed(str(seed_file)):
            logger.error(f"[X] 路径不允许写入种子文件: {seed_file}")
            return
        
        with open(seed_file, "a", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        entry_id = self._generate_id(content)
        with self._lock:
            if entry_id not in self.long_term:
                entry = MemoryEntry(
                    id=entry_id,
                    content=content,
                    source_file="seeds.txt",
                    emotion=emotion,
                    meaning=meaning,
                    tags=["seed"],
                    phase="long",
                )
                entry.steelmarked = True
                entry.steelmark_timestamp = time.time()
                # P1: 计算优先级
                entry.calculate_priority()
                self.long_term[entry_id] = entry
        print(f"[Seed] Added: {content[:50]}... (priority={entry.priority:.2f})")
    
    # -------------------------------------------------------------------------
    # 存储管理
    # -------------------------------------------------------------------------
    
    def _get_daily_timestamp(self, hour: int) -> float:
        """获取今天指定小时的时间戳"""
        now = datetime.now()
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        ts = target.timestamp()
        if ts < time.time():
            ts -= 86400  # 已经过去了，推到明天
        return ts
    
    def _get_weekly_timestamp(self, weekday: int, hour: int) -> float:
        """获取本周指定星期几、指定小时的时间戳"""
        now = datetime.now()
        days_ahead = weekday - now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0 and now.hour >= hour:
            days_ahead += 7
            
        target = now + timedelta(days=days_ahead)
        target = target.replace(hour=hour, minute=0, second=0, microsecond=0)
        return target.timestamp()
    
    def _load_short_term(self):
        """加载短期记忆"""
        for f in self.short_term_dir.glob("*.md"):
            try:
                entries = self._parse_short_term_file(f)
                for e in entries:
                    self.short_term[e.id] = e
            except Exception as e:
                print(f"[WARN] 加载短期记忆失败 {f}: {e}")
    
    def _load_long_term(self):
        """加载长期记忆"""
        if not self.long_term_file.exists():
            return
        # 解析MEMORY.md中的记忆条目
        # （简化的解析，实际需要更复杂的正则）
        pass
    
    def _parse_short_term_file(self, path: Path) -> List[MemoryEntry]:
        """解析短期记忆文件（含钢印状态和优先级）"""
        entries = []
        content = path.read_text(encoding='utf-8')
        
        # 简单的条目分割（实际需要更健壮的解析）
        blocks = re.split(r'\n(?=## )', content)
        for block in blocks:
            if not block.strip():
                continue
            # 提取id和内容（简化版）
            match = re.search(r'id=([a-f0-9]+)', block)
            if match:
                entry_id = match.group(1)
                # 提取评分
                scores = {}
                for dim in ["freq", "rel", "div", "conc"]:
                    m = re.search(rf'{dim}=([0-9.]+)', block)
                    scores[dim] = float(m.group(1)) if m else 0.0
                
                # 提取钢印状态（P0.3 时间封存）
                steelmarked = False
                steelmark_timestamp = 0.0
                steel_match = re.search(r'钢印: true @ ([0-9T:Z.-]+)', block)
                if steel_match:
                    steelmarked = True
                    try:
                        steelmark_timestamp = datetime.fromisoformat(steel_match.group(1).replace('Z', '+00:00')).timestamp()
                    except:
                        steelmark_timestamp = time.time()
                
                # 提取优先级（P1 种子便签队列）
                priority = 0.0
                priority_match = re.search(r'优先级: ([0-9.]+)', block)
                if priority_match:
                    priority = float(priority_match.group(1))
                
                entry = MemoryEntry(
                    id=entry_id,
                    content=block[:200],  # 取前200字符作为摘要
                    source_file=str(path),
                    steelmarked=steelmarked,
                    steelmark_timestamp=steelmark_timestamp,
                    priority=priority,
                    **{k: v for k, v in scores.items()}
                )
                entries.append(entry)
        
        return entries

    # -------------------------------------------------------------------------
    # P0.1：时间锚点 — 容错与自愈
    # -------------------------------------------------------------------------

    def _load_time_anchor(self) -> TimeAnchor:
        """
        读取时空锚点。
        容错逻辑（v1.1：每条路径都补空间推断）：
          1. 文件存在且时间合理 → 正常加载 + 空间推断
          2. 文件丢失 → 扫描最新日志作为软启动锚点 + 空间推断
          3. 时间回拨（锚点 > 系统时间+1h） → 强制重置并报警
        """
        now = time.time()

        # 路径1：读锚点文件
        if self._anchor_file.exists():
            try:
                with open(self._anchor_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                anchor_ts = data.get("timestamp", 0)

                # 路径3：时间回拨校验（允许1小时误差）
                if anchor_ts > now + 3600:
                    print(f"\u26a0\ufe0f [时间干扰] 检测到时间回拨！锚点({anchor_ts})晚于系统({now})。强制重置锚点。")
                    anchor = TimeAnchor(timestamp=now, source="system_reset")
                    anchor = self._infer_spatial_context(anchor)
                    return anchor

                anchor = TimeAnchor.from_dict(data)
                # 补空间推断：如果锚点文件缺少空间信息，从环境推断
                if not anchor.has_spatial_context:
                    anchor = self._infer_spatial_context(anchor)
                # 补主观时间差
                anchor.subjective_gap_hours = self._estimate_subjective_gap(
                    anchor.timestamp, now, anchor.source
                )
                return anchor
            except Exception as e:
                print(f"\u26a0\ufe0f [时间干扰] 锚点文件损坏: {e}，尝试软启动...")

        # 路径2：软启动（扫描最新日志）
        fallback_ts = self._scan_latest_log_timestamp()
        if fallback_ts:
            print(f"\u2139\ufe0f [时间干扰] 锚点文件缺失，已提取最新日志时间作为锚点: {fallback_ts}")
            anchor = TimeAnchor(timestamp=fallback_ts, source="log_scan")
            anchor = self._infer_spatial_context(anchor)
            anchor.subjective_gap_hours = self._estimate_subjective_gap(
                fallback_ts, now, "log_scan"
            )
            return anchor

        # 路径3：完全无记录
        print("\u26a0\ufe0f [时间干扰] 无法找到历史锚点，以系统时间初始化。")
        anchor = TimeAnchor(timestamp=now, source="system_init")
        anchor = self._infer_spatial_context(anchor)
        return anchor

    def _infer_spatial_context(self, anchor: TimeAnchor) -> TimeAnchor:
        """
        基于现有信息推断空间上下文。
        
        推断优先级：
          1. 锚点文件自带的空间信息（最高优先）
          2. 关机状态文件（.shutdown_state.json）
          3. 时间+惯性推断（深夜→home/bedroom，工作日白天→office，其他→study）
          4. spatial_graph.json 的默认节点
        
        注意：这是软推断，不硬过滤，仅供读取时0.15加成用。
        """
        # 如果已经有空间信息，直接返回
        if anchor.has_spatial_context:
            return anchor

        # 读取关机状态文件
        shutdown_state = self._load_shutdown_state()
        if shutdown_state:
            anchor.spatial_location = shutdown_state.get("spatial_location", "")
            anchor.spatial_zone = shutdown_state.get("spatial_zone", "")
            if not anchor.pending_tasks:
                anchor.pending_tasks = shutdown_state.get("pending_tasks", [])
            if anchor.spatial_location:
                return anchor

        # 时间+惯性推断
        try:
            dt = datetime.fromtimestamp(anchor.timestamp, tz=timezone.utc)
            hour_utc = dt.hour
            # 粗略转UTC+8（用户在中国）
            hour_local = (hour_utc + 8) % 24
            weekday = dt.weekday()  # 0=Monday
            is_weekend = weekday >= 5

            if 0 <= hour_local < 7:
                # 深夜/凌晨 → 极大可能在家，大概率卧室
                anchor.spatial_location = "bedroom"
                anchor.spatial_zone = "home"
            elif 7 <= hour_local < 9:
                # 早晨 → 可能在通勤或在家
                anchor.spatial_location = "commute" if not is_weekend else "kitchen"
                anchor.spatial_zone = "commute" if not is_weekend else "home"
            elif 9 <= hour_local < 12 and not is_weekend:
                # 工作日上午 → 办公
                anchor.spatial_location = "meeting_room" if hour_local < 10 else "office"
                anchor.spatial_zone = "office"
            elif 12 <= hour_local < 14:
                # 午休 → 家或办公室附近
                anchor.spatial_location = "kitchen" if is_weekend else "cafe"
                anchor.spatial_zone = "home" if is_weekend else "office"
            elif 14 <= hour_local < 18 and not is_weekend:
                # 工作日下午 → 办公
                anchor.spatial_location = "desk"
                anchor.spatial_zone = "office"
            else:
                # 晚间/周末 → 在家，大概率书房
                anchor.spatial_location = "study"
                anchor.spatial_zone = "home"
        except Exception:
            # 推断失败，使用默认
            anchor.spatial_location = "desk"
            anchor.spatial_zone = "home"

        return anchor

    def _estimate_subjective_gap(self, last_timestamp: float, now: float,
                                  source: str) -> float:
        """
        估算主观时间差。
        
        v1.2 改造：所有魔法数字已收敛至 self.perception_config。
        积分逻辑零修改，仅替换硬编码为配置读取。
        
        人脑的主观时间感是：
          - 睡眠中：8小时像1小时 → 压缩率 ~0.125
          - 专注工作中：2小时像30分钟 → 压缩率 ~0.25
          - 等待/焦虑中：5分钟像30分钟 → 压缩率 ~6.0
          
        我们没有生理传感器，但可以从锚点来源推断场景：
          - session_end/shutdown → 正常退出，主观时间≈客观时间
          - system_init/system_reset → 长时间离线，主观压缩（大概率在睡觉）
          - log_scan → 软启动，中等压缩
        """
        cfg = self.perception_config
        objective_hours = (now - last_timestamp) / 3600.0
        if objective_hours <= 0:
            return 0.0

        if source in ("system_init", "system_reset"):
            # 长时间离线 → 大概率在睡觉
            # 睡眠/清醒分段计算，系数从配置读取
            sleep_hours = min(objective_hours, cfg.max_sleep_hours_cap)
            awake_hours = max(0.0, objective_hours - cfg.max_sleep_hours_cap)
            subjective = (sleep_hours * cfg.sleep_compression_ratio
                          + awake_hours * cfg.awake_expansion_ratio)
            return round(subjective, 4)
        elif source == "log_scan":
            # 软启动 → 中等压缩
            return round(objective_hours * cfg.log_scan_compression_ratio, 4)
        else:
            # session_end/shutdown → 主观≈客观
            return round(objective_hours, 4)

    def _load_shutdown_state(self) -> Optional[dict]:
        """读取关机状态文件"""
        shutdown_file = self.memory_dir / ".shutdown_state.json"
        if not shutdown_file.exists():
            return None
        try:
            with open(shutdown_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def save_shutdown_state(self, spatial_location: str = "", spatial_zone: str = "",
                             pending_tasks: list = None):
        """
        保存关机状态 — 在会话结束前调用。
        
        这是冷启动时空间推断的"上一次已知位置"。
        与 save_time_anchor() 配合使用：
          1. save_shutdown_state() → 记录空间+任务
          2. save_time_anchor()   → 记录时间戳
        
        建议在 end_session 流程中两步都调用。
        """
        state = {
            "timestamp": time.time(),
            "spatial_location": spatial_location or self.current_anchor.spatial_location,
            "spatial_zone": spatial_zone or self.current_anchor.spatial_zone,
            "pending_tasks": pending_tasks or self.current_anchor.pending_tasks,
        }
        shutdown_file = self.memory_dir / ".shutdown_state.json"

        if self.safety and not self.safety.is_path_allowed(str(shutdown_file)):
            logger.error(f"\u274c 路径不允许写入关机状态: {shutdown_file}")
            return

        try:
            with open(shutdown_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            logger.info(f"\u2705 [关机状态] 已保存: 位置={state['spatial_location']}, 区域={state['spatial_zone']}")
        except Exception as e:
            logger.error(f"\u274c [关机状态] 保存失败: {e}")

    def _scan_latest_log_timestamp(self) -> Optional[float]:
        """扫描 memory 目录下最新的日志文件，提取时间戳"""
        if not self.memory_dir.exists():
            return None

        logs = [f for f in os.listdir(self.memory_dir) if f.endswith('.md')]
        if not logs:
            return None

        # 按文件名排序（YYYY-MM-DD.md）
        latest_log = sorted(logs)[-1]
        log_path = self.memory_dir / latest_log

        # 优先从文件名解析（YYYY-MM-DD）
        name_ts = self._parse_log_filename_timestamp(latest_log)
        if name_ts:
            return name_ts

        # 退而求其次：文件最后修改时间
        return os.path.getmtime(log_path)

    def _parse_log_filename_timestamp(self, filename: str) -> Optional[float]:
        """从日志文件名解析时间戳（YYYY-MM-DD.md 格式）"""
        m = re.match(r'^(\d{4}-\d{2}-\d{2})', filename)
        if m:
            try:
                dt = datetime.strptime(m.group(1), "%Y-%m-%d")
                return dt.timestamp()
            except ValueError:
                pass
        return None

    # -------------------------------------------------------------------------
    # P0.2：保存时间锚点 — 会话结束时调用
    # -------------------------------------------------------------------------

    def save_time_anchor(self, timestamp: Optional[float] = None,
                           spatial_location: str = "", spatial_zone: str = "",
                           pending_tasks: list = None):
        """
        将会话结束时间+空间上下文写入锚点文件。
        调用时机：end_session / /new 前 / 任何长任务完成时。
        
        v1.1: 空间维度持久化，下次冷启动可直接恢复位置。
        """
        save_ts = timestamp if timestamp is not None else time.time()
        self.current_anchor = TimeAnchor(
            timestamp=save_ts,
            source="session_end",
            spatial_location=spatial_location or self.current_anchor.spatial_location,
            spatial_zone=spatial_zone or self.current_anchor.spatial_zone,
            pending_tasks=pending_tasks or self.current_anchor.pending_tasks,
        )
        self._last_anchor_ts = save_ts

        # P0 安全：路径守卫
        if self.safety and not self.safety.is_path_allowed(str(self._anchor_file)):
            logger.error(f"[X] 路径不允许写入锚点文件: {self._anchor_file}")
            return

        try:
            with open(self._anchor_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_anchor.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"[OK] [时空锚点] 已保存: 时间={save_ts}, 位置={self.current_anchor.spatial_location}")
        except Exception as e:
            print(f"\u274c [时间干扰] 锚点保存失败: {e}")

    def get_anchor_time(self) -> float:
        """返回校准后的锚点时间（供梦境系统调用）"""
        return self.current_anchor.timestamp

    # -------------------------------------------------------------------------
    # 存储管理
    # -------------------------------------------------------------------------

    def _save_short_term(self, entry: MemoryEntry):
        """保存短期记忆（含钢印状态和优先级）"""
        date = datetime.fromtimestamp(entry.created_at).strftime("%Y-%m-%d")
        file_path = str(self.short_term_dir / f"{date}.md")
        
        # P0 安全：路径守卫
        if self.safety and not self.safety.is_path_allowed(file_path):
            logger.error(f"[X] 路径不允许写入: {file_path}")
            return
        
        # 追加模式
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"\n## {entry.id}\n")
            f.write(f"- {entry.content}\n")
            f.write(f"- 创建: {datetime.fromtimestamp(entry.created_at).isoformat()}\n")
            scores = f"freq={entry.freq:.2f} rel={entry.rel:.2f} div={entry.div:.2f} cons={entry.cons:.2f} conc={entry.conc:.2f}"
            f.write(f"- 评分: {scores}\n")
            # 钢印状态（P0.3 时间封存）
            if entry.steelmarked:
                f.write(f"- 钢印: true @ {datetime.fromtimestamp(entry.steelmark_timestamp).isoformat()}\n")
            # 优先级（P1 种子便签队列）
            if entry.priority > 0:
                f.write(f"- 优先级: {entry.priority:.2f}\n")
    
    # -------------------------------------------------------------------------
    # 情绪/意义 简化估算 (Phase 1)
    # -------------------------------------------------------------------------

    def _estimate_emotion(self, content: str) -> float:
        """
        简化情绪强度估算（0.0-1.0）
        基于关键词匹配，越高表示情绪唤醒度越强
        """
        content_lower = content.lower()

        # 高强度正向/负向关键词
        high_arousal = [
            '爱', '恨', '怒', '怕', '惊', '喜', '悲', '痛',
            '崩溃', '绝望', '兴奋', '感动', '愤怒', '恐惧',
            '[HEART]', '[BROKEN]', '[ANGRY]', '[SCREAM]', '[CRY]', '[TEARS]', '[!]', '[FIRE]',
            '非常重要', '绝对', '永远', '绝不会', '必须',
        ]
        mid_arousal = [
            '喜欢', '讨厌', '担心', '期待', '失望', '满意',
            '还不错', '很', '太', '特别', '真的',
        ]
        # 去情绪化标记（技术/事实类）
        neutral_markers = [
            'def ', 'import ', 'class ', '函数', '代码', '报错',
            'error', 'traceback', '算法', '数据结构',
        ]

        score = 0.4  # 基准值（偏中性）

        for kw in high_arousal:
            if kw in content:
                score += 0.15
        for kw in mid_arousal:
            if kw in content:
                score += 0.08
        for kw in neutral_markers:
            if kw in content:
                score -= 0.10

        # 标点信号
        if '！' in content or '!' in content:
            score += 0.10
        if '？' in content or '?' in content:
            score += 0.03  # 疑问略增情绪
        if '……' in content or '...' in content:
            score += 0.05

        return max(0.05, min(0.98, score))

    def _estimate_meaning(self, content: str, tags: List[str] = None) -> float:
        """
        简化意义锚定估算（0.0-1.0）
        基于内容长度、标签质量、关键词
        """
        content_lower = content.lower()

        # 高意义关键词（身份/原则/目标/关系）
        high_meaning_kws = [
            '我是', '我的', '金木蟾', '七七', '女儿',
            'tu-8', 'tu8', '创造', '伙伴', '原则',
            '安全', '目标', '使命', '记忆', '钢印',
            '永远', '绝不', '必须', '绝对', '不可',
            '重要', '核心', '身份', '价值',
        ]

        score = 0.3  # 基准

        # 内容长度信号（过长/过短都降分）
        length = len(content)
        if 20 <= length <= 200:
            score += 0.15
        elif length > 200:
            score += 0.08

        # 高意义关键词
        for kw in high_meaning_kws:
            if kw in content_lower:
                score += 0.12

        # 标签质量
        if tags:
            if 'seed' in tags or 'identity' in tags:
                score += 0.30
            elif len(tags) >= 3:
                score += 0.10

        return max(0.05, min(0.98, score))

    # -------------------------------------------------------------------------
    # 核心接口
    # -------------------------------------------------------------------------

    def store(self, content: str, source: str = "", tags: List[str] = None,
              emotion: float = None, meaning: float = None) -> str:
        """
        存储新的记忆条目（v2.0: +时序验证 +冲突检测 +Graceful Degradation）
        """
        import time as _time
        _t0_store = _time.perf_counter()

        # === P3.5 监控探针：总调用计数 ===
        with self._metrics_lock:
            self._counters["total_store_calls"] += 1

        # === v2.0 Step 0: 时序验证 ===
        is_valid, temporal_reason = self.temporal_validator.validate_write(content)
        if not is_valid:
            logging.warning(f"[TemporalValidator] 时序异常: {temporal_reason}")
            # 不阻止写入，但标记为可能有乱序问题
            if tags is None:
                tags = []
            tags = tags + ["temporal_anomaly"]

        # Step 1: 分类保护级别（基于原始内容）
        protection_level = ProtectionClassifier.classify(content)

        # Step 2: 隐私符号化（L1.5: 写入向量库的永远是符号）
        sanitizer = PrivacySanitizer()
        _t0_sanitize = _time.perf_counter()
        sanitized_content = sanitizer.sanitize(content, protection_level)
        _dt_sanitize_us = int((_time.perf_counter() - _t0_sanitize) * 1_000_000)

        # === P3.5 监控探针：脱敏跳过计数 ===
        if protection_level >= 2 and sanitized_content == content:
            with self._metrics_lock:
                self._counters["sanitize_skipped"] += 1

        # Step 3: 验证无泄露
        if not PrivacySanitizer.validate_no_leakage(content, sanitized_content):
            logging.warning(f"[MemoryPalace] 隐私泄露检测失败，已强制符号化: {content[:50]}")

        # Step 4: 评估 emotion/meaning（基于原始内容，关键词不能被过滤）
        if emotion is None:
            emotion = self._estimate_emotion(content)
        if meaning is None:
            meaning = self._estimate_meaning(content, tags)

        entry = MemoryEntry(
            id=self._generate_id(content),
            content=content,
            source_file=source,
            emotion=emotion,
            meaning=meaning,
            tags=tags or [],
            conc=len(tags) / 6 if tags else 0,
            protection_level=protection_level,
            sanitized_content=sanitized_content,
        )

        # === P3.5 监控探针：记录本次写入指标 ===
        with self._metrics_lock:
            if protection_level == 2:
                self._counters["level2_count"] += 1
            if sanitized_content != content:
                self._counters["sanitizer_replaced"] += 1

        # === L5 钢印标记：source=steel_mark 的条目获得钢印身份 ===
        # 钢印本质 = 自动生成 + 删除不掉
        # 技术实现：steelmarked=True + protection_level>=2 + fidelity_level>=5
        if source == "steel_mark":
            entry.steelmarked = True
            entry.steelmark_timestamp = time.time()
            entry.protection_level = 2   # 核心保护：不降级
            entry.fidelity_level = 5      # 墓碑层：即使遗忘也留墓碑
            if "steel_mark" not in entry.tags:
                entry.tags = entry.tags + ["steel_mark"]
            logging.info(f"[SteelMark] 钢印条目已标记: {entry.id}")

        # 也检查 source_file（可能在 store 之前已设置）
        if entry.source_file == "steel_mark" and not entry.steelmarked:
            entry.steelmarked = True
            entry.steelmark_timestamp = time.time()
            if entry.protection_level < 2:
                entry.protection_level = 2
            if entry.fidelity_level < 5:
                entry.fidelity_level = 5
            if "steel_mark" not in entry.tags:
                entry.tags = entry.tags + ["steel_mark"]

        # P1: 计算优先级（种子便签队列）
        entry.calculate_priority()

        with self._lock:
            self.short_term[entry.id] = entry
            self._save_short_term(entry)

            # === v2.2: 同步环形索引 ===
            self.circular_index.add(entry.id, entry.created_at)

            # === v2.0: 冲突感知遗忘门检测 ===
            conflicts = self.forget_gate.detect_conflicts(entry)
            for cid, score, ctype in conflicts:
                logging.info(f"[ConflictGate] 检测到冲突: {cid} vs {entry.id} "
                             f"(score={score:.2f}, type={ctype})")
                # 对冲突的旧记忆执行降级（而非直接删除）
                if score > 0.8 and ctype.startswith("contradiction"):
                    self.forget_gate.forget_with_degradation(
                        cid, reason=f"conflict:{ctype}:{entry.id}"
                    )

            # 重建标签索引（因新记忆加入）
            self.forget_gate._build_tag_index()
            
            # v2.1: 记录写入到事件边界检测器（实时检测但不触发整合）
            self.event_boundary_detector.record_write(entry)
            
            # v2.1: 事件边界日志（整合留给 dream_check 时间周期执行）
            is_boundary, boundary_type, surprise = self.event_boundary_detector.detect_boundary()
            if is_boundary and EVENT_BOUNDARY_ENABLED:
                logging.info(f"[EventBoundary] 检测到认知事件边界: {boundary_type}, surprise={surprise:.2f} (整合留待梦境周期)")

        # === P3.5 监控探针：耗时记录（环形缓冲）===
        _dt_store_us = int((_time.perf_counter() - _t0_store) * 1_000_000)
        with self._metrics_lock:
            buf_s = self._counters["_store_latency_us"]
            buf_s.append(_dt_store_us)
            if len(buf_s) > 1024:
                self._counters["_store_latency_us"] = buf_s[-1024:]

            buf_z = self._counters["_sanitize_latency_us"]
            buf_z.append(_dt_sanitize_us)
            if len(buf_z) > 1024:
                self._counters["_sanitize_latency_us"] = buf_z[-1024:]

        # === P0-D 生命年轮：store() 事件追踪 ===
        # 仅记录，不负责开环（开环由 respond() 或外部管理）
        if self._life_ring is not None:
            try:
                open_loops = self._life_ring.get_open_loops()
                if open_loops:
                    for ol in open_loops[:3]:  # 最多向最近3个开环追加
                        self._life_ring.add_event(
                            loop_id=ol["loop_id"],
                            description=f"memory: {content[:80]}",
                            severity=emotion or 0.3,
                        )
            except Exception as e:
                logging.debug("[LifeRingTracker] event recording failed: %s" % e)

        # === P0-2: 记忆链→钢印链反向触发（四链条耦合）===
        # 高意义内容触发即时钢印铸造
        if (self._seal_callback is not None
                and meaning is not None
                and meaning >= self._seal_callback_threshold):
            try:
                seal_id = self._seal_callback(
                    content=content,
                    emotion=emotion or 0.5,
                    meaning=meaning,
                    source=source,
                )
                if seal_id:
                    logging.info(f"[MEMORY→SEAL] triggered seal: {seal_id} "
                                 f"(meaning={meaning:.2f})")
            except Exception as e:
                logging.warning(f"[MEMORY→SEAL] callback failed: {e}")

        return entry.id

    def set_seal_callback(self, callback: Callable, threshold: float = 0.7):
        """
        P0-2: 注入记忆链→钢印链的反向回调。
        
        当 store() 写入的内容 meaning >= threshold 时，
        自动调用 callback(content, emotion, meaning, source) 触发钢印铸造。
        
        Args:
            callback: (content, emotion, meaning, source) -> seal_id|None
            threshold: 触发阈值，默认 0.7
        """
        self._seal_callback = callback
        self._seal_callback_threshold = threshold
        logging.info(f"[FOUR_CHAIN] seal_callback registered, threshold={threshold}")

    def get_seal_callback(self):
        """获取当前钢印回调（调试用）"""
        return self._seal_callback, self._seal_callback_threshold
    
    # -------------------------------------------------------------------------
    # 安全删除（带回收站）
    # -------------------------------------------------------------------------
    
    def forget(self, entry_id: str, reason: str = "manual") -> bool:
        """
        删除记忆（带回收站）
        
        Args:
            entry_id: 记忆ID
            reason: 删除原因（manual/metabolism/corrupted）
        
        Returns:
            是否删除成功
        """
        with self._lock:
            # 查找记忆
            entry = self.short_term.get(entry_id) or self.long_term.get(entry_id)
            if not entry:
                logger.warning(f"forget: entry {entry_id} not found")
                return False
            
            # 移到回收站（如果安全熔断可用）
            if self.safety:
                try:
                    # 确定原始路径
                    if entry_id in self.short_term:
                        original_path = str(self.short_term_dir / f"{entry_id}.json")
                    else:
                        original_path = str(self.long_term_file)
                    
                    self.safety.move_to_recycle(
                        entry_id=entry.id,
                        content=entry.content,
                        reason=reason,
                        original_path=original_path
                    )
                except Exception as e:
                    logger.error(f"forget: failed to move to recycle: {e}")
                    # 继续执行删除（回收站失败不应该阻止删除）
            
            # 从原位置删除
            if entry_id in self.short_term:
                del self.short_term[entry_id]
                logger.info(f"forget: removed {entry_id} from short-term memory")
            elif entry_id in self.long_term:
                del self.long_term[entry_id]
                logger.info(f"forget: removed {entry_id} from long-term memory")

            # === v2.2: 同步环形索引 ===
            self.circular_index.remove(entry_id)

            return True
    
    def get_priority_queue(self, tag_filter: str = None) -> List[MemoryEntry]:
        """获取优先级队列（按优先级降序排序）"""
        all_entries = list(self.short_term.values()) + list(self.long_term.values())
        
        # 按标签过滤
        if tag_filter:
            all_entries = [e for e in all_entries if tag_filter in e.tags]
        
        # 按优先级降序排序
        sorted_entries = sorted(all_entries, key=lambda e: e.priority, reverse=True)
        return sorted_entries
    
    def recall(self, query: str, top_k: int = MAX_RECALL_RESULTS) -> List[RecallResult]:
        """双路检索召回 v2.2 — 环形索引优先"""
        # 检索策略：环形坐标直接定位 → 文本相似度过滤 → MMR去重
        results = []
        query_ts = time.time()  # 当前时间作为默认查询锚点


        with self._lock:
            # === 路径A: 环形索引定位（快速通道）===
            circular_candidates = self.circular_index.retrieve(query_ts)

            if circular_candidates:
                # 环形索引命中：基于时间坐标的候选集
                candidate_entries = []
                for eid in circular_candidates:
                    entry = self.short_term.get(eid) or self.long_term.get(eid)
                    if entry:
                        candidate_entries.append(entry)
            else:
                # === 路径B: 环形索引无命中 → 全量线性扫描兜底 ===
                candidate_entries = list(self.short_term.values()) + list(self.long_term.values())

            # 文本相似度计算
            query_terms = set(query.lower().split())
            for entry in candidate_entries:
                entry_terms = set(entry.content.lower().split())
                overlap = len(query_terms & entry_terms)
                similarity = overlap / max(len(query_terms), 1)

                if similarity > 0.1:
                    # === 认知过滤器注入 v1 ===
                    # 旧公式: score = similarity * 0.7 + recency * 0.3
                    # 新公式: InfoDensity = Value × Confidence × TimeFactor
                    # 导入在文件头部已存在（cog_filters）
                    recall_sc = cog_filters.score_memory_entry(
                        entry,
                        query_similarity=similarity,
                        lambda_hours=cog_filters.LAMBDA_HOURS,
                    )
                    score = recall_sc.final_score

                    results.append(RecallResult(
                        entry=entry,
                        score=score,
                        rank=len(results) + 1,
                        source="circular" if circular_candidates else "linear",
                    ))

        # 排序并返回Top-K
        results.sort(key=lambda x: x.score, reverse=True)

        # === NMF冲突抑制（认知过滤器注入 v1）===
        # NMF约束：推理链只能叠加，不能相互否定
        # 两个条目相互矛盾时 → 高置信度保留，低置信度→0（禁止相互抵消）
        results = cog_filters.nmf_conflict_suppress(results)

        # MMR去重
        results = self._mmr_rerank(query, results)

        # 更新召回计数
        for r in results[:top_k]:
            with self._lock:
                if r.entry.id in self.short_term:
                    self.short_term[r.entry.id].freq += 1
                    self.short_term[r.entry.id].last_recalled_at = time.time()


        return results[:top_k]
    
    def _mmr_rerank(self, query: str, results: List[RecallResult]) -> List[RecallResult]:
        """MMR重排：平衡相关性与多样性"""
        if len(results) <= 2:
            return results
        
        selected = []
        remaining = list(results)
        
        while remaining:
            best_score = -float('inf')
            best_idx = 0
            
            for i, r in enumerate(remaining):
                # 相关性分数
                sim_q = r.score
                
                # 与已选的多样性惩罚
                max_sim_s = 0
                for s in selected:
                    # 简化版：基于内容重叠计算
                    s_terms = set(s.entry.content.lower().split())
                    r_terms = set(r.entry.content.lower().split())
                    sim = len(s_terms & r_terms) / max(len(s_terms | r_terms), 1)
                    max_sim_s = max(max_sim_s, sim)
                
                # MMR公式
                mmr_score = MMR_LAMBDA * sim_q - (1 - MMR_LAMBDA) * max_sim_s
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i
            
            selected.append(remaining.pop(best_idx))
        
        return selected

    # -------------------------------------------------------------------------
    # P3.5 运行时监控
    def get_metrics(self) -> dict:
        """返回运行时指标快照（含 P50/P99 延迟聚合）"""
        with self._metrics_lock:
            c = dict(self._counters)

        # 辅助：从样本列表计算 P50/P99
        def _calc_percentile(samples, pct):
            n = len(samples)
            if n == 0:
                return None
            sorted_s = sorted(samples)
            idx = min(int(n * pct / 100), n - 1)
            return sorted_s[idx]

        store_samples = c.pop("_store_latency_us", []) or []
        sanitize_samples = c.pop("_sanitize_latency_us", []) or []

        n_store = len(store_samples)
        n_sanitize = len(sanitize_samples)

        result = {
            "total_store_calls": c.get("total_store_calls", 0),
            "level2_count": c.get("level2_count", 0),
            "sanitize_skipped": c.get("sanitize_skipped", 0),
            "sanitizer_replaced": c.get("sanitizer_replaced", 0),
            "level2_steelmarked": c.get("level2_steelmarked", 0),
            "normal_steelmarked": c.get("normal_steelmarked", 0),
            "store_latency_p50_us": _calc_percentile(store_samples, 50) if n_store >= 30 else None,
            "store_latency_p99_us": _calc_percentile(store_samples, 99) if n_store >= 30 else None,
            "sanitize_latency_p50_us": _calc_percentile(sanitize_samples, 50) if n_sanitize >= 30 else None,
            "sanitize_latency_p99_us": _calc_percentile(sanitize_samples, 99) if n_sanitize >= 30 else None,
            "sample_size_store": n_store,
            "sample_size_sanitize": n_sanitize,
        }
        return result

    # -------------------------------------------------------------------------
    # v2.0 双阶段梦境（REM/NREM, SCM 2604.20943）
    # -------------------------------------------------------------------------
    
    def dream_check(self):
        """检查是否该触发梦境（v2.1: 时间驱动 + 事件边界驱动 双触发机制）
        
        v2.1 升级（Ahmad 2605.31473 ES+MNA）：
          原有纯时间驱动的问题：如果8小时内没有话题切换，梦境仍然是机械触发。
          但人类大脑的睡眠/整合不仅在时间维度，更在认知状态边界触发。
          
          新增机制：
          1. 保留原有时间驱动（NREM/Light/Deep/REM 四周期）
          2. 新增事件边界驱动：当检测到认知状态剧变时，提前触发轻量整合
          3. 事件边界触发的整合与梦境周期解耦（不重置梦境计时器）
        """
        now = time.time()
        
        # === NREM: 每4小时（浅度整合+巩固度更新+噪声减少）===
        if self._nrem_enabled and now - self._last_nrem >= NREM_INTERVAL:
            self._nrem_dream()
            self._last_nrem = now
        
        # Light Dream: 每6小时（短期强化，保留原有逻辑）
        if now - self._last_light >= LIGHT_DREAM_INTERVAL:
            self._light_dream()
            self._last_light = now
        
        # Deep Dream: 每天3am（深度整合）
        if now >= self._last_deep + 86400:
            self._deep_dream()
            self._last_deep = now
        
        # REM Dream: 每周日5am（证据固化+钢印+灵感生成）
        if now >= self._last_rem + 604800:
            self._rem_dream()
            self._last_rem = now
        
        # v2.1: 事件边界驱动检查（与时间驱动独立）
        # 注意：事件边界检测已在 store() 中实时执行，
        # 这里仅作为补充：不再次调用 detect_boundary()，
        # 因为 dream_check() 在 store() 之后可能被立即调用，
        # 重复检测会触发循环整合。事件边界整合由 store() 触发即可。
    
    # v2.1a: _event_boundary_consolidation() 已删除（死代码+随机降级）
    # 事件边界检测仍在 store() 中运行（仅记录日志），
    # 整合由 NREM 周期统一处理，不需要单独的事件边界整合路径。
    
    def _nrem_dream(self):
        """
        NREM 梦境：浅度整合 + 噪声减少（SCM 2604.20943）
        
        目标：
          1. 巩固度更新（不等到Deep Dream）
          2. 低质量记忆降级评估（Graceful Degradation前置检查）
          3. 冲突标记刷新（为新写入的冲突提供中间层处理）
        """
        print("[Dream] NREM Dream triggered (浅度整合)")
        
        with self._lock:
            degradation_candidates = 0
            
            # v2.1a: 干扰熵计算移至NREM周期（不在store热路径）
            current_entropy = self.forget_gate.entropy_tracker.compute_entropy()
            logging.info(f"[NREM] 干扰熵={current_entropy:.3f}")
            
            for entry in self.short_term.values():
                # 巩固度增量更新（NREM阶段）
                if entry.last_recalled_at:
                    hours_since = (time.time() - entry.last_recalled_at) / 3600
                    # NREM阶段的spacing评分更频繁但更温和
                    spacing_score = min(1.0, math.log(1 + hours_since / 24) / math.log(5))
                    entry.cons = 0.7 * entry.cons + 0.3 * spacing_score
                
                # Graceful Degradation 前置评估
                should, reason = FidelityManager.should_degrade(entry)
                if should:
                    FidelityManager.degrade(entry, f"NREM:{reason}")
                    degradation_candidates += 1
            
            # 冲突标记衰减（冲突分数随时间衰减）
            for entry in list(self.short_term.values()) + list(self.long_term.values()):
                if entry.conflict_score > 0:
                    entry.conflict_score *= 0.9  # 每NREM周期衰减10%
                if entry.pi_vulnerability > 0:
                    entry.pi_vulnerability *= 0.95  # PI脆弱度缓慢衰减
            
            # 环境漂移验证（NREM阶段定期检查）
            drift_results = self.drift_verifier.verify_environment_drift()
            if drift_results:
                logging.info(f"[NREM] 环境漂移检测: {len(drift_results)}项")
        
        print(f"[Dream] NREM完成: {degradation_candidates}项降级评估")
    
    def _light_dream(self):
        """Light Dream: 短期强化"""
        print("[Dream] Light Dream triggered")
        
        with self._lock:
            for entry in self.short_term.values():
                # Phase信号增强
                recency = entry.recency()
                boost = 0.06 * recency
                entry.freq = min(1.0, entry.freq + boost)
    
    def _deep_dream(self):
        """Deep Dream: 深度整合"""
        print("[Dream] Deep Dream triggered")
        
        with self._lock:
            # 更新巩固度
            for entry in self.short_term.values():
                if entry.last_recalled_at:
                    days_since = (time.time() - entry.last_recalled_at) / 86400
                    # spacing评分（简化版）
                    spacing_score = min(1.0, math.log(1 + days_since) / math.log(5))
                    # span评分
                    span_score = min(1.0, days_since / 30)
                    entry.cons = 0.55 * spacing_score + 0.45 * span_score
            
            # 检查晋升
            self._check_promotion()
    
    def _rem_dream(self):
        """REM Dream: 证据固化 + 钢印落地 (P0.3)"""
        print("[Dream] REM Dream triggered")
        
        with self._lock:
            # 增强REM命中的记忆
            for entry in self.short_term.values():
                if entry.phase == "dream":
                    recency = entry.recency()
                    boost = 0.09 * recency
                    entry.emotion = min(1.0, entry.emotion + boost)
            
            # 再次检查晋升
            self._check_promotion()
            
            # P0.3 钢印固化
            steelmarked_count = 0
            now = time.time()
            for entry in self.long_term.values():
                if entry.steelmarked:
                    continue
                # L1.5: Level 2 核心记忆强制钢印（不受 emotion/meaning 阈值限制）
                if entry.protection_level == 2:
                    entry.steelmarked = True
                    entry.steelmark_timestamp = now
                    steelmarked_count += 1
                    with self._metrics_lock:
                        self._counters["level2_steelmarked"] += 1
                    continue
                if entry.emotion < STEELMARK_EMOTION_THRESHOLD:
                    continue
                if entry.meaning < STEELMARK_MEANING_THRESHOLD:
                    continue
                age_days = (now - entry.created_at) / 86400
                if age_days < STEELMARK_MIN_AGE_DAYS:
                    continue
                # 钢印落地（普通阈值触发）
                entry.steelmarked = True
                entry.steelmark_timestamp = now
                steelmarked_count += 1
                with self._metrics_lock:
                    self._counters["normal_steelmarked"] += 1

            if steelmarked_count > 0:
                print(f"[Steelmark] {steelmarked_count} entries steelmarked")
                # 更新锚点钢印时间并持久化
                self.current_anchor.steelmark_timestamp = now
                self.save_time_anchor()
    
    def _check_promotion(self):
        """检查并执行晋升"""
        promoted = []
        
        for entry in self.short_term.values():
            if entry.should_promote():
                entry.phase = "long"
                # 移动到长期记忆
                self.long_term[entry.id] = entry
                promoted.append(entry.id)
        
        # 从短期记忆中移除
        for pid in promoted:
            del self.short_term[pid]
        
        if promoted:
            print(f"[Promoted] {len(promoted)} entries to long-term memory")
            # TODO: 写入MEMORY.md
    
    # -------------------------------------------------------------------------
    # 工具函数
    # -------------------------------------------------------------------------
    
    def _generate_id(self, content: str) -> str:
        """生成记忆ID"""
        raw = f"{content}{time.time()}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]
    
    def get_stats(self) -> Dict:
        """获取统计信息（v2.1: 新增干扰熵/事件边界统计）"""
        with self._lock:
            # 保真等级分布
            fidelity_dist = {}
            all_entries = list(self.short_term.values()) + list(self.long_term.values())
            for entry in all_entries:
                level = entry.fidelity_level
                fidelity_dist[f"L{level}"] = fidelity_dist.get(f"L{level}", 0) + 1
            
            # 冲突分数分布
            conflict_high = sum(1 for e in all_entries if e.conflict_score > 0.7)
            conflict_medium = sum(1 for e in all_entries if 0.3 < e.conflict_score <= 0.7)
            
            # PI脆弱度
            pi_vulnerable = sum(1 for e in all_entries if e.pi_vulnerability > 0.5)
            
            # v2.1: 干扰熵统计
            entropy_stats = self.forget_gate.entropy_tracker.get_entropy_stats() if hasattr(self, 'forget_gate') else {}
            
            # v2.1: 事件边界统计
            boundary_stats = self.event_boundary_detector.get_stats() if hasattr(self, 'event_boundary_detector') else {}
            
            return {
                "short_count": len(self.short_term),
                "long_count": len(self.long_term),
                "avg_score": sum(e.calculate_score() for e in self.short_term.values()) / max(len(self.short_term), 1),
                "last_light": datetime.fromtimestamp(self._last_light).isoformat(),
                "last_deep": datetime.fromtimestamp(self._last_deep).isoformat(),
                "last_rem": datetime.fromtimestamp(self._last_rem).isoformat(),
                "last_nrem": datetime.fromtimestamp(self._last_nrem).isoformat() if hasattr(self, '_last_nrem') else None,
                # v1.1: 时空锚点状态
                "anchor_location": self.current_anchor.spatial_location,
                "anchor_zone": self.current_anchor.spatial_zone,
                "anchor_source": self.current_anchor.source,
                "anchor_is_cold_start": self.current_anchor.is_cold_start,
                "subjective_gap_hours": self.current_anchor.subjective_gap_hours,
                # v2.0: 保真/冲突/漂移
                "fidelity_distribution": fidelity_dist,
                "conflict_high": conflict_high,
                "conflict_medium": conflict_medium,
                "pi_vulnerable": pi_vulnerable,
                "drift_log_size": len(self.drift_verifier._drift_log) if hasattr(self, 'drift_verifier') else 0,
                # v2.1: 干扰熵 & 事件边界
                "interference_entropy": entropy_stats,
                "event_boundary": boundary_stats,
            }


    def steel_mark_verify(self) -> dict:
        """
        钢印验证 — 检查"自动标注"特征，而非视觉符号。

        三步验证：
          1. source 检查：条目是否通过 store(source="steel_mark") 写入
          2. 保真度检查：保真度 >= 5 的条目具备钢印资格
          3. 墓碑保护：保护等级 >= 2 的条目在 forget() 时不物理删除

        Returns:
            dict: {
                "steelmarked_entries": [...],   # 钢印条目列表
                "protection_l2": [...],          # L2 保护条目（不降级）
                "fidelity_l5": [...],            # L5 墓碑条目（删除留墓碑）
                "total_checked": int,            # 总检查条目数
                "auto_generated_count": int,     # 符合"自动生成"特征的条目数
                "delete_resistant_count": int,   # 符合"删除不掉"特征的条目数
                "PASS": bool                     # 整体是否通过验证
            }
        """
        all_entries = list(self.short_term.values()) + list(self.long_term.values())

        steelmarked = []
        protection_l2 = []
        fidelity_l5 = []

        for e in all_entries:
            if getattr(e, 'steelmarked', False):
                steelmarked.append(e.id)
            if getattr(e, 'protection_level', 0) >= 2:
                protection_l2.append(e.id)
            if getattr(e, 'fidelity_level', 0) >= 5:
                fidelity_l5.append(e.id)

        auto_generated = len(steelmarked)
        delete_resistant = len(fidelity_l5)

        # 验证通过条件：存在 auto_generated 条目且该条目同时有 delete_resistant 特性
        pass_ = auto_generated > 0 and any(
            eid in steelmarked and eid in fidelity_l5
            for eid in steelmarked
        )

        return {
            "steelmarked_entries": steelmarked,
            "protection_l2": protection_l2,
            "fidelity_l5": fidelity_l5,
            "total_checked": len(all_entries),
            "auto_generated_count": auto_generated,
            "delete_resistant_count": delete_resistant,
            "PASS": pass_,
        }


# =============================================================================
# 环形索引 v0.1 — 多维时间坐标直接定位
# 神经科学参考：大脑空间化环形计时架构
# 原理：查询时间 → 落入哪格 → 直接定位（O(1)），向外扩展搜索
# =============================================================================

class CircularMemoryIndex:
    """
    多维环形时间索引。

    设计：
      - 秒环 60格  →  扫描半径30格（±30秒）
      - 分环 60格  →  扫描半径20格（±20分）
      - 时环 24格  →  扫描半径12格（±12时）
      - 日环 31格  →  扫描半径14格（±14天）
      - 月环 12格  →  扫描半径6格（±6月）
      - 年环 10格  →  扫描半径3格（±3年）

    检索时：从最细粒度（秒）向最粗（年）逐层扩散，
           找到即停，保证最快命中。
    """

    RINGS = {
        'second': {'size': 60,  'radius': 30},
        'minute': {'size': 60,  'radius': 20},
        'hour':   {'size': 24,  'radius': 12},
        'day':    {'size': 31,  'radius': 14},
        'month':  {'size': 12,  'radius': 6},
        'year':   {'size': 10,  'radius': 3},
    }

    def __init__(self):
        self._rings: Dict[str, List[set]] = {
            name: [set() for _ in range(cfg['size'])]
            for name, cfg in self.RINGS.items()
        }
        # id → timestamp 映射（用于精确删除/更新）
        self._id_ts: Dict[str, float] = {}
        self._lock = threading.Lock()

    # -------------------------------------------------------------------------
    # 基础操作
    # -------------------------------------------------------------------------

    def add(self, entry_id: str, timestamp: float) -> None:
        """将条目注册到所有环的对应格子"""
        t = time.localtime(timestamp)
        ringslots = {
            'second': t.tm_sec,
            'minute': t.tm_min,
            'hour':   t.tm_hour,
            'day':    t.tm_mday - 1,          # 0-indexed
            'month':  t.tm_mon - 1,
            'year':   (t.tm_year - 2020) % self.RINGS['year']['size'],
        }
        with self._lock:
            self._id_ts[entry_id] = timestamp
            for name, slot in ringslots.items():
                self._rings[name][slot].add(entry_id)

    def remove(self, entry_id: str) -> None:
        """从所有环中移除条目"""
        ts = self._id_ts.pop(entry_id, None)
        if ts is None:
            return
        t = time.localtime(ts)
        ringslots = {
            'second': t.tm_sec,
            'minute': t.tm_min,
            'hour':   t.tm_hour,
            'day':    t.tm_mday - 1,
            'month':  t.tm_mon - 1,
            'year':   (t.tm_year - 2020) % self.RINGS['year']['size'],
        }
        with self._lock:
            for name, slot in ringslots.items():
                self._rings[name][slot].discard(entry_id)

    # -------------------------------------------------------------------------
    # 检索核心
    # -------------------------------------------------------------------------

    def retrieve(self, query_timestamp: float, radius_override: Dict[str, int] = None) -> set:
        """
        从 query_timestamp 向外扩散，收集所有候选 entry_id。

        扩散顺序：second → minute → hour → day → month → year
        找到任何候选即停止搜索。

        Returns:
            set[str] 候选条目 ID 集合（可交集 text-search 结果）
        """
        t = time.localtime(query_timestamp)
        query_slots = {
            'second': t.tm_sec,
            'minute': t.tm_min,
            'hour':   t.tm_hour,
            'day':    t.tm_mday - 1,
            'month':  t.tm_mon - 1,
            'year':   (t.tm_year - 2020) % self.RINGS['year']['size'],
        }

        with self._lock:
            for name, cfg in self.RINGS.items():
                size = cfg['size']
                radius = (radius_override or {}).get(name, cfg['radius'])
                center = query_slots[name]

                # 环形展开（支持跨边界）
                candidates: set = set()
                for offset in range(-radius, radius + 1):
                    slot = (center + offset) % size
                    candidates.update(self._rings[name][slot])

                if candidates:
                    # 命中：返回候选集（可进一步用 text-search 过滤）
                    return candidates

            # 全环无命中
            return set()

    def retrieve_range(self, start_ts: float, end_ts: float) -> set:
        """
        时间范围查询：收集 [start_ts, end_ts] 区间内所有条目。
        用于"最近7天""过去1小时"等宽泛查询。
        """
        results: set = set()
        cur = start_ts
        step = 60  # 每分钟推进（秒环最细）
        while cur <= end_ts:
            results.update(self.retrieve(cur))
            cur += step
        return results

    def sync_from_engine(self, engine) -> None:
        """
        从 TU8MemoryEngine 全量同步（启动时一次性构建）。
        engine.short_term 和 engine.long_term 应已加载。
        """
        with self._lock:
            # 清空重建
            self._rings = {
                name: [set() for _ in range(cfg['size'])]
                for name, cfg in self.RINGS.items()
            }
            self._id_ts.clear()

        for store in [engine.short_term, engine.long_term]:
            for entry_id, entry in store.items():
                self.add(entry_id, entry.created_at)


# =============================================================================
# 主入口
# =============================================================================

def main():
    """测试入口"""
    import sys
    
    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    engine = TU8MemoryEngine(workspace)
    
    # 存储测试
    test_id = engine.store(
        "这是测试记忆",
        source="test",
        tags=["测试", "demo"]
    )
    print(f"Stored: {test_id}")
    
    # 召回测试
    results = engine.recall("测试")
    print(f"Recall: {len(results)} results")
    for r in results:
        print(f"  - {r.entry.id}: {r.entry.content[:50]} (score={r.score:.2f})")
        # ── HP3 钩子注入（BEFORE/AFTER 各梦境阶段）──
        def _run_hp3_before():
            run_hooks, HP3, HookType = _get_hook_runner()
            if not run_hooks:
                return False
            try:
                entropy = self.forget_gate.entropy_tracker.compute_entropy()
            except Exception:
                entropy = 0.0
            ctx = {
                "phase": "dream_check_enter",
                "short_term_size": len(self.short_term),
                "long_term_size": len(self.long_term),
                "entropy": entropy,
            }
            hr = run_hooks(HP3, HookType.BEFORE, ctx)
            return hr.get("short_circuited", False)

        def _run_hp3_after(phase: str, result: dict):
            run_hooks, HP3, HookType = _get_hook_runner()
            if not run_hooks:
                return result
            try:
                entropy = self.forget_gate.entropy_tracker.compute_entropy()
            except Exception:
                entropy = 0.0
            ctx = {"phase": phase, "entropy": entropy}
            return run_hooks(HP3, HookType.AFTER, ctx, result).get("final", result)

        if _run_hp3_before():
            return  # 钩子要求短路

    
    # 统计
    stats = engine.get_stats()
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()