# tu8_memory.py - TU-8 记忆系统核心
# 版本：v1.2 | 日期：2026-05-30 | 基于OpenClaw记忆系统逆向成果
# 标签：#记忆蒸馏 #三层梦境 #双路检索 #六维晋升

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
        self._load_seeds()
    
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
            logger.error(f"❌ 路径不允许写入种子文件: {seed_file}")
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
            logger.error(f"❌ 路径不允许写入锚点文件: {self._anchor_file}")
            return

        try:
            with open(self._anchor_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_anchor.to_dict(), f, indent=2, ensure_ascii=False)
            logger.info(f"✅ [时空锚点] 已保存: 时间={save_ts}, 位置={self.current_anchor.spatial_location}")
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
            logger.error(f"❌ 路径不允许写入: {file_path}")
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
            '❤', '💔', '😡', '😱', '😭', '🥹', '❗', '🔥',
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
            '我是', '我的', '李奥', '七七', '女儿',
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
        存储新的记忆条目（L1.5 新增：隐私分类+符号化）
        """
        import time as _time
        _t0_store = _time.perf_counter()

        # === P3.5 监控探针：总调用计数 ===
        with self._metrics_lock:
            self._counters["total_store_calls"] += 1

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

        # P1: 计算优先级（种子便签队列）
        entry.calculate_priority()

        with self._lock:
            self.short_term[entry.id] = entry
            self._save_short_term(entry)

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

        return entry.id
    
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
        """双路检索召回"""
        # 这里需要实际的embedding和BM25实现
        # 简化版：只用文本匹配
        
        results = []
        
        with self._lock:
            all_entries = list(self.short_term.values()) + list(self.long_term.values())
            
            # 简单文本匹配（Placeholder: 需要向量搜索+BM25）
            for i, entry in enumerate(all_entries):
                # 计算简单相似度
                query_terms = set(query.lower().split())
                entry_terms = set(entry.content.lower().split())
                overlap = len(query_terms & entry_terms)
                similarity = overlap / max(len(query_terms), 1)
                
                if similarity > 0.1:
                    # 应用时间衰减
                    recency = entry.recency()
                    score = similarity * 0.7 + recency * 0.3
                    
                    results.append(RecallResult(
                        entry=entry,
                        score=score,
                        rank=len(results) + 1,
                        source="mixed"
                    ))
        
        # 排序并返回Top-K
        results.sort(key=lambda x: x.score, reverse=True)
        
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
    # 三层梦境
    # -------------------------------------------------------------------------
    
    def dream_check(self):
        """检查是否该触发梦境"""
        now = time.time()
        
        # Light Dream: 每6小时
        if now - self._last_light >= LIGHT_DREAM_INTERVAL:
            self._light_dream()
            self._last_light = now
        
        # Deep Dream: 每天3am
        if now >= self._last_deep + 86400:  # 一天只触发一次
            self._deep_dream()
            self._last_deep = now
        
        # REM Dream: 每周日5am
        if now >= self._last_rem + 604800:  # 一周只触发一次
            self._rem_dream()
            self._last_rem = now
    
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
        """获取统计信息"""
        with self._lock:
            return {
                "short_count": len(self.short_term),
                "long_count": len(self.long_term),
                "avg_score": sum(e.calculate_score() for e in self.short_term.values()) / max(len(self.short_term), 1),
                "last_light": datetime.fromtimestamp(self._last_light).isoformat(),
                "last_deep": datetime.fromtimestamp(self._last_deep).isoformat(),
                "last_rem": datetime.fromtimestamp(self._last_rem).isoformat(),
                # v1.1: 时空锚点状态
                "anchor_location": self.current_anchor.spatial_location,
                "anchor_zone": self.current_anchor.spatial_zone,
                "anchor_source": self.current_anchor.source,
                "anchor_is_cold_start": self.current_anchor.is_cold_start,
                "subjective_gap_hours": self.current_anchor.subjective_gap_hours,
            }


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
    
    # 统计
    stats = engine.get_stats()
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()