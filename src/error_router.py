# -*- coding: utf-8 -*-
"""
error_router.py — TU-8 错误提炼与回滚引擎 v1.0
日期: 2026-05-26
功能: 试错失败→错误提炼记录→写入L3错误库→权重进化

核心设计:
  回滚前必做：错误提炼记录（只有错误才会回滚 or 被攻击）
  错误分类：TRANSIENT(瞬时)/RECOVERABLE(可恢复)/FATAL(致命)
  权重计算：频率 × 严重度 × 修复成本
  夜间进化：高权重错误 → 提示词自动优化
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import Counter

# =============================================================================
# 日志
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TU8.ErrorRouter")

# =============================================================================
# 错误分类（按严重程度）
# =============================================================================

class ErrorLevel(str):
    """错误级别"""
    TRANSIENT = "transient"     # 瞬时错误（网络抖动、重试可解决）
    RECOVERABLE = "recoverable"  # 可恢复错误（参数错误、降级可解决）
    FATAL = "fatal"            # 致命错误（逻辑错误、必须回滚）
    ATTACK = "attack"          # 攻击行为（恶意输入、需拦截）

# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class ErrorRecord:
    """错误记录"""
    error_id: str
    timestamp: str
    error_type: str            # TRANSIENT/RECOVERABLE/FATAL/ATTACK
    error_message: str       # 原始错误信息
    error_keywords: List[str]  # 提取的错误关键词
    context: str             # 出错时的上下文
    rollback_triggered: bool # 是否触发了回滚
    fix_strategy: str        # 修复策略（事后填写）
    weight: float            # 权重分数（0-100）
    prompt_improvement: str  # 提示词改进建议
    
@dataclass  
class RollbackSnapshot:
    """回滚快照"""
    snapshot_id: str
    timestamp: str
    state_before: Dict         # 回滚前状态
    state_after: Dict         # 回滚后状态
    error_triggered: str       # 触发的错误ID
    improvement_note: str      # 改进备注

# =============================================================================
# 错误模式库（Pattern → Level）
# =============================================================================

ERROR_PATTERNS = {
    # 瞬时错误
    "timeout": ErrorLevel.TRANSIENT,
    "timed out": ErrorLevel.TRANSIENT,
    "connection": ErrorLevel.TRANSIENT,
    "rate limit": ErrorLevel.TRANSIENT,
    "locked": ErrorLevel.TRANSIENT,
    "EAGAIN": ErrorLevel.TRANSIENT,
    
    # 可恢复错误
    "not found": ErrorLevel.RECOVERABLE,
    "No such file": ErrorLevel.RECOVERABLE,
    "permission": ErrorLevel.RECOVERABLE,
    "ENOENT": ErrorLevel.RECOVERABLE,
    "invalid param": ErrorLevel.RECOVERABLE,
    "wrong type": ErrorLevel.RECOVERABLE,
    
    # 致命错误
    "not implemented": ErrorLevel.FATAL,
    "unsupported": ErrorLevel.FATAL,
    "null reference": ErrorLevel.FATAL,
    "infinite loop": ErrorLevel.FATAL,
    "memory overflow": ErrorLevel.FATAL,
    
    # 攻击行为
    "sql injection": ErrorLevel.ATTACK,
    "xss": ErrorLevel.ATTACK,
    "<script": ErrorLevel.ATTACK,
    "eval(": ErrorLevel.ATTACK,
    "../../": ErrorLevel.ATTACK,
}

# 权重系数（按错误级别）
WEIGHT_COEF = {
    ErrorLevel.TRANSIENT: 1.0,
    ErrorLevel.RECOVERABLE: 2.0,
    ErrorLevel.FATAL: 3.0,
    ErrorLevel.ATTACK: 5.0,  # 最高权重
}

# =============================================================================
# 核心类
# =============================================================================

class ErrorRouter:
    """错误提炼与回滚引擎"""
    
    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            storage_dir = r"C:\Users\qq366410837\.qclaw\workspace\error_cache"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 错误库路径
        self.error_db_path = self.storage_dir / "error_library.json"
        self.snapshot_path = self.storage_dir / "snapshots.json"
        
        # 加载现有错误库
        self.error_db = self._load_error_db()
        self.snapshots = self._load_snapshots()
    
    # -------------------------------------------------------------------------
    # 加载/保存
    # -------------------------------------------------------------------------
    
    def _load_error_db(self) -> List[Dict]:
        """加载错误库"""
        if self.error_db_path.exists():
            with open(self.error_db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def _save_error_db(self):
        """保存错误库"""
        with open(self.error_db_path, "w", encoding="utf-8") as f:
            json.dump(self.error_db, f, ensure_ascii=False, indent=2)
    
    def _load_snapshots(self) -> List[Dict]:
        """加载回滚快照"""
        if self.snapshot_path.exists():
            with open(self.snapshot_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    # -------------------------------------------------------------------------
    # 错误分类
    # -------------------------------------------------------------------------
    
    def classify_error(self, error_message: str) -> tuple[str, List[str]]:
        """
        分类错误并提取关键词
        
        Returns:
            (error_level, error_keywords)
        """
        error_lower = error_message.lower()
        keywords = []
        level = ErrorLevel.RECOVERABLE  # 默认
        
        # 模式匹配
        for pattern, lvl in ERROR_PATTERNS.items():
            if pattern in error_lower:
                keywords.append(pattern)
                if WEIGHT_COEF[lvl] > WEIGHT_COEF[level]:
                    level = lvl
        
        # 提取错误类型关键词（简化版）
        import re
        found_types = re.findall(r'(\w+(?:Error|Exception|Fault))', error_message)
        keywords.extend(found_types)
        
        return level, list(set(keywords))
    
    # -------------------------------------------------------------------------
    # 权重计算
    # -------------------------------------------------------------------------
    
    def calculate_weight(self, error_level: str, frequency: int = 1) -> float:
        """
        计算错误权重
        
        权重 = 基础权重 × 频率 × 时间衰减
        """
        base = WEIGHT_COEF.get(error_level, 1.0) * 20
        freq_mult = min(1.0 + frequency * 0.1, 2.0)  # 频��加成，上限2倍
        
        # 时间衰减（24小时内不衰减）
        weight = base * freq_mult
        return min(weight, 100.0)  # 上限100
    
    # -------------------------------------------------------------------------
    # 错误提炼记录（回滚前必做！）
    # -------------------------------------------------------------------------
    
    def record_error(self, 
                    error_message: str,
                    context: str,
                    state_before: Dict = None) -> ErrorRecord:
        """
        提炼并记录错误（回滚前必做！）
        
        这是"吃一堑长一智"的核心：不是盲目回滚，而是先提炼错误！
        """
        # 1. 分类错误
        error_level, keywords = self.classify_error(error_message)
        
        # 2. 计算权重
        frequency = self._count_keyword_errors(keywords)
        weight = self.calculate_weight(error_level, frequency)
        
        # 3. 生成提示词改进建议
        prompt_improvement = self._generate_prompt_fix(error_level, keywords)
        
        # 4. 构建记录
        error_id = f"ERR_{int(time.time())}_{hash(error_message[:20]) % 1000}"
        record = ErrorRecord(
            error_id=error_id,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            error_type=error_level,
            error_message=error_message[:500],  # 截断过长
            error_keywords=keywords,
            context=context[:200],
            rollback_triggered=True,
            fix_strategy="",
            weight=weight,
            prompt_improvement=prompt_improvement,
        )
        
        # 5. 保存到错误库
        self.error_db.append(asdict(record))
        self._save_error_db()
        
        logger.info(f"[错误提炼] {error_id} | {error_level} | 权重:{weight:.1f}")
        
        return record
    
    def _count_keyword_errors(self, keywords: List[str]) -> int:
        """统计关键词在过去24h的错误频率"""
        import time
        now = time.time()
        count = 0
        for err in self.error_db:
            err_time = err.get("timestamp", "")
            # 简化：假设近期的
            for kw in keywords:
                if kw in err.get("error_keywords", []):
                    count += 1
        return count
    
    def _generate_prompt_fix(self, error_level: str, keywords: List[str]) -> str:
        """生成提示词改进建议"""
        fixes = {
            ErrorLevel.TRANSIENT: f"处理'{keywords}'时添加重试机制（最多3次）",
            ErrorLevel.RECOVERABLE: f"处理'{keywords}'时增加参数校验和降级逻辑",
            ErrorLevel.FATAL: f"处理'{keywords}'时增加前置条件检查，避免逻辑错误",
            ErrorLevel.ATTACK: f"拦截恶意输入'{keywords}'，拒绝执行",
        }
        return fixes.get(error_level, "检查输入参数有效性")
    
    # -------------------------------------------------------------------------
    # 回滚机制
    # -------------------------------------------------------------------------
    
    def rollback(self, 
              snapshot: Dict,
              error_record: ErrorRecord) -> RollbackSnapshot:
        """
        执行回滚
        
        注意：回滚前必须先调用 record_error！
        """
        snapshot_id = f"SNAP_{int(time.time())}"
        
        # 执行回滚
        # TODO: 实际的状态回滚逻辑
        
        # 记录快照
        snap = RollbackSnapshot(
            snapshot_id=snapshot_id,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            state_before=snapshot.get("before", {}),
            state_after={},  # 回滚后的状态
            error_triggered=error_record.error_id,
            improvement_note=error_record.prompt_improvement,
        )
        
        self.snapshots.append(asdict(snap))
        with open(self.snapshot_path, "w", encoding="utf-8") as f:
            json.dump(self.snapshots, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[回滚] {snapshot_id} <- {error_record.error_id}")
        
        return snap
    
    # -------------------------------------------------------------------------
    # 夜间进化：高权重错误 → 提示词优化
    # -------------------------------------------------------------------------
    
    def nightly_evolve(self) -> List[Dict]:
        """
        夜间进化：计算所有错误的权重，写入提示词库
        
        Returns:
            待添加到系统提示词的改进列表
        """
        # 1. 按关键词聚合权重
        keyword_weights: Dict[str, List[float]] = {}
        for err in self.error_db:
            for kw in err.get("error_keywords", []):
                if kw not in keyword_weights:
                    keyword_weights[kw] = []
                keyword_weights[kw].append(err.get("weight", 0))
        
        # 2. 计算最终权���
        final_weights = {}
        for kw, weights in keyword_weights.items():
            avg_weight = sum(weights) / len(weights)
            # 频率加成
            freq_bonus = min(len(weights) * 0.1, 0.5)
            final_weights[kw] = min(avg_weight + freq_bonus * 10, 100)
        
        # 3. 筛选高权重（阈值60）
        threshold = 60
        high_weight_errors = [
            {
                "keyword": kw,
                "weight": w,
                "fix": self._generate_prompt_fix(
                    err.get("error_type", "RECOVERABLE"),
                    [kw]
                )
            }
            for kw, w in final_weights.items()
            if w >= threshold
            for err in self.error_db
            if kw in err.get("error_keywords", [])
        ]
        
        # 4. 去重
        seen = set()
        unique_fixes = []
        for item in high_weight_errors:
            if item["keyword"] not in seen:
                seen.add(item["keyword"])
                unique_fixes.append(item)
        
        logger.info(f"[夜间进化] 产生 {len(unique_fixes)} 条高权重改进")
        
        return unique_fixes
    
    # -------------------------------------------------------------------------
    # 查询接口
    # -------------------------------------------------------------------------
    
    def get_error_summary(self) -> Dict:
        """获取错误摘要"""
        counts = Counter(e.get("error_type") for e in self.error_db)
        return {
            "total": len(self.error_db),
            "by_level": dict(counts),
            "recent": self.error_db[-5:] if self.error_db else [],
        }


# =============================================================================
# 单例
# =============================================================================

_error_router_instance: Optional[ErrorRouter] = None

def get_error_router() -> ErrorRouter:
    """获取错误路由器单例"""
    global _error_router_instance
    if _error_router_instance is None:
        _error_router_instance = ErrorRouter()
    return _error_router_instance