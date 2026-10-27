# -*- coding: utf-8 -*-
# streak_calculator.py — TU-8 连击计算器 v1.0
# 版本：v1.0 | 创建：2026-05-15 | 基于：Streak_Rules.md v1.0
# 用途：单用户连击系统（基于事件驱动）
# 存储：本地JSON文件（无数据库依赖）

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from pathlib import Path

# ============================================================
# 配置
# ============================================================

class Config:
    """连击系统配置（来源：monitoring_config.yaml + Streak_Rules.md）"""
    
    # 文件路径
    STREAK_STATUS_FILE = "D:/qq366410837/.qclaw/workspace/knowledge/TU-8/streak_status.json"
    PAIN_STATUS_FILE = "D:/qq366410837/.qclaw/workspace/pain_status.json"
    DEFENSE_LOG_FILE = "D:/qq366410837/.qclaw/workspace/knowledge/TU-8/defense-log.md"
    
    # 熵增系数衰减表
    ENTROPHY_PHASES = [
        {"name": "活跃期",  "max_hours": 12,  "k_entropy": 1.0,  "decay_rate": 0.0},
        {"name": "冷却期",  "max_hours": 36,  "k_entropy": 0.9,  "decay_rate": 0.05},  # 每12h降0.05
        {"name": "衰退期",  "max_hours": 60,  "k_entropy": 0.6,  "decay_rate": 0.15},  # 每12h降0.15
        {"name": "熔断期",  "max_hours": None, "k_entropy": 0.0,  "decay_rate": None},
    ]
    
    # 连击加成系数
    STREAK_BONUS = [
        {"min_streak": 0,  "max_streak": 4,  "s_multiplier": 1.0, "phase": "新手期"},
        {"min_streak": 5,  "max_streak": 9,  "s_multiplier": 1.1, "phase": "成长期"},
        {"min_streak": 10, "max_streak": 19, "s_multiplier": 1.2, "phase": "稳定期"},
        {"min_streak": 20, "max_streak": 999, "s_multiplier": 1.3, "phase": "荣耀期"},
    ]
    
    # 护盾等级
    SHIELD_LEVELS = [
        {"min_streak": 0,  "max_streak": 4,  "level": 0, "name": "无护盾"},
        {"min_streak": 5,  "max_streak": 9,  "level": 1, "name": "新手护盾"},
        {"min_streak": 10, "max_streak": 19, "level": 2, "name": "标准护盾"},
        {"min_streak": 20, "max_streak": 999, "level": 3, "name": "荣耀护盾"},
    ]
    
    # 保鲜期（小时）
    FRESHNESS_HOURS_WORKDAY = 24
    FRESHNESS_HOURS_WEEKEND = 48
    
    # 熔断阈值
    MELTDOWN_HOURS = 60  # >60h 强制归零
    
    # 积分公式参数
    SCORE_BASE = 10  # 基础积分
    
    # 勋章解锁阈值
    MEDAL_THRESHOLDS = {
        "🔰 新手连击": 5,
        "⚔️ 连击战士": 10,
        "🛡️ 连击守护者": 20,
        "🔥 连击大师": 50,
        "👑 连击传奇": 100,
    }


# ============================================================
# 工具函数
# ============================================================

def load_json(path: str) -> Dict:
    """加载JSON文件，文件不存在则返回空字典"""
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path: str, data: Dict) -> None:
    """保存JSON文件（自动创建目录）"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now() -> str:
    """返回当前UTC时间 ISO格式"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

def parse_time(ts: str) -> datetime:
    """解析ISO时间字符串"""
    return datetime.fromisoformat(ts.replace('Z', '+00:00'))

def hours_since(ts: str) -> float:
    """计算从时间戳到现在的小时数"""
    if not ts:
        return 0.0  # 首次运行，视为0小时，不触发熔断
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        now_dt = datetime.now(timezone.utc)
        return max(0.0, (now_dt - dt).total_seconds() / 3600)
    except Exception:
        return 0.0  # 解析失败，视为0小时，不触发熔断

def is_weekend() -> bool:
    """判断今天是否是周末"""
    return datetime.now(timezone.utc).weekday() >= 5


# ============================================================
# 熵增系数计算
# ============================================================

def calc_k_entropy(elapsed_hours: float) -> float:
    """
    计算熵增系数 K_entropy
    非线性衰减：
    0-12h:  活跃期 K=1.0
    12-36h: 冷却期 每12h降0.05
    36-60h: 衰退期 每12h降0.15
    >60h:   熔断   K=0.0
    """
    if elapsed_hours <= 12:
        return 1.0
    elif elapsed_hours <= 36:
        decay_intervals = int((elapsed_hours - 12) / 12)
        return max(0.0, 1.0 - 0.05 * decay_intervals)
    elif elapsed_hours <= 60:
        # 已完成冷却期衰减0.10，再按衰退期计算
        remaining_intervals = int((elapsed_hours - 36) / 12)
        return max(0.0, 0.90 - 0.15 * remaining_intervals)
    else:
        return 0.0


# ============================================================
# 连击加成系数
# ============================================================

def calc_s_multiplier(streak: int) -> Dict[str, Any]:
    """计算连击加成系数 S_streak"""
    for tier in Config.STREAK_BONUS:
        if tier["min_streak"] <= streak <= tier["max_streak"]:
            return tier
    return Config.STREAK_BONUS[-1]  # 默认荣耀期

def calc_shield_level(streak: int) -> Dict[str, Any]:
    """计算当前护盾等级"""
    for tier in Config.SHIELD_LEVELS:
        if tier["min_streak"] <= streak <= tier["max_streak"]:
            return tier
    return Config.SHIELD_LEVELS[-1]


# ============================================================
# 勋章系统
# ============================================================

def check_new_medals(old_streak: int, new_streak: int) -> list:
    """检查是否有新解锁的勋章"""
    new_medals = []
    for medal, threshold in Config.MEDAL_THRESHOLDS.items():
        if old_streak < threshold <= new_streak:
            new_medals.append(medal)
    return new_medals


# ============================================================
# 连击计算器核心类
# ============================================================

class StreakCalculator:
    """
    TU-8 连击计算器
    
    用法示例：
    calc = StreakCalculator()
    
    # 用户完成了一个任务
    result = calc.on_task_completed(task_type="design", quality_score=0.9)
    print(result)
    
    # 用户发了一条消息（即使不是任务）
    calc.on_interaction()
    
    # 查询当前状态
    status = calc.get_status()
    print(f"连击: {status['current_streak']}, 阶段: {status['phase']}")
    """
    
    def __init__(self, user_id: str = "default_user"):
        self.user_id = user_id
        self.status_file = Config.STREAK_STATUS_FILE
        self._ensure_status_file()
    
    def _ensure_status_file(self) -> None:
        """确保状态文件存在（初始化默认状态）"""
        if not os.path.exists(self.status_file):
            default_state = {
                "user_id": self.user_id,
                "current_streak": 0,
                "last_active_time": None,
                "k_entropy": 1.0,
                "shield_level": 0,
                "shield_status": 1,  # 1=完好, 0=已破碎
                "earned_medals": [],
                "total_tasks_completed": 0,
                "total_score": 0,
                "frozen": False,
                "melted": False,  # 熔断后是否被用户重新激活
                "last_update": now(),
            }
            save_json(self.status_file, default_state)
    
    def _load_status(self) -> Dict:
        """加载当前状态"""
        return load_json(self.status_file)
    
    def _save_status(self, status: Dict) -> None:
        """保存状态"""
        status["last_update"] = now()
        save_json(self.status_file, status)
    
    def on_interaction(self) -> Dict[str, Any]:
        """
        用户产生任意交互时调用（发消息、完成任务等）
        返回当前状态摘要
        """
        status = self._load_status()
        status["last_active_time"] = now()
        status["melted"] = False  # 任何交互都重置熔断状态
        self._save_status(status)
        return self.get_status()
    
    def on_task_completed(
        self,
        task_type: str = "general",
        quality_score: float = 1.0,
        bonus: float = 1.0,
    ) -> Dict[str, Any]:
        """
        任务完成时调用
        
        参数：
        - task_type: 任务类型（影响基础积分）
        - quality_score: 质量评分 0.0-1.0
        - bonus: 其他加成因子
        
        返回：完整的结果报告
        """
        status = self._load_status()
        old_streak = status["current_streak"]
        
        # 步骤1：计算熵增系数
        elapsed_hours = hours_since(status["last_active_time"])
        k_entropy = calc_k_entropy(elapsed_hours)
        
        # 步骤2：判断是否熔断
        if elapsed_hours > Config.MELTDOWN_HOURS:
            return self._trigger_meltdown(status, task_type, quality_score, bonus)
        
        # 步骤3：计算新连击数
        # 只有活跃期和冷却期才增长，衰退期不增长但也不归零
        if k_entropy > 0:
            new_streak = old_streak + 1
        else:
            # 衰退期：归零但保留记录
            new_streak = 0
        
        # 步骤4：计算加成系数
        s_info = calc_s_multiplier(new_streak)
        s_multiplier = s_info["s_multiplier"]
        
        # 步骤5：计算积分
        score_base = Config.SCORE_BASE
        score_raw = score_base * k_entropy * quality_score * s_multiplier * bonus
        score_final = round(score_raw, 1)
        
        # 步骤6：检查护盾升级
        old_shield = calc_shield_level(old_streak)
        new_shield = calc_shield_level(new_streak)
        
        # 步骤7：检查新勋章
        new_medals = check_new_medals(old_streak, new_streak)
        earned_medals = list(set(status["earned_medals"] + new_medals))
        
        # 步骤8：更新状态
        status["current_streak"] = new_streak
        status["last_active_time"] = now()
        status["k_entropy"] = k_entropy
        status["shield_level"] = new_shield["level"]
        # 护盾升级后重置为完好（除非已被用户打破）
        if new_shield["level"] > old_shield["level"]:
            status["shield_status"] = 1
        status["earned_medals"] = earned_medals
        status["total_tasks_completed"] += 1
        status["total_score"] = round(status["total_score"] + score_final, 1)
        status["frozen"] = False
        status["melted"] = False
        self._save_status(status)
        
        # 返回结果
        return {
            "success": True,
            "streak_before": old_streak,
            "streak_after": new_streak,
            "phase": s_info["phase"],
            "s_multiplier": s_multiplier,
            "k_entropy": round(k_entropy, 2),
            "score_earned": score_final,
            "total_score": status["total_score"],
            "shield_level": new_shield["name"],
            "shield_status": "完好" if status["shield_status"] == 1 else "已破碎",
            "new_medals": new_medals,
            "quality_score": quality_score,
            "elapsed_hours": round(elapsed_hours, 1),
        }
    
    def on_mild_negative(
        self,
        reason: str = "用户主观不认可"
    ) -> Dict[str, Any]:
        """
        遭遇轻微负面反馈时调用（护盾保护检查）
        
        来源：Streak_Rules.md 七、红绿灯 vs 连击
        """
        status = self._load_status()
        
        if status["shield_status"] == 1 and status["shield_level"] > 0:
            # 护盾完好，消耗护盾
            status["shield_status"] = 0
            self._save_status(status)
            return {
                "blocked": True,
                "shield_consumed": True,
                "streak_preserved": True,
                "shield_level": calc_shield_level(status["current_streak"])["name"],
                "message": f"护盾挡下了本次负面反馈 [{reason}]",
            }
        else:
            # 无护盾保护，连击归零
            old_streak = status["current_streak"]
            status["current_streak"] = 0
            status["shield_status"] = 0
            status["shield_level"] = 0
            self._save_status(status)
            return {
                "blocked": False,
                "shield_consumed": False,
                "streak_preserved": False,
                "streak_lost": old_streak,
                "message": f"无护盾保护，连击归零 [{reason}]",
            }
    
    def on_principle_error(
        self,
        reason: str = "原则性错误"
    ) -> Dict[str, Any]:
        """
        遭遇原则性错误时调用（护盾无法保护）
        
        来源：Streak_Rules.md 六、轻微负面 vs 原则性错误
        红线清单：核心文件删除、环境破坏、死循环、欺骗、隐瞒、越狱
        """
        status = self._load_status()
        old_streak = status["current_streak"]
        
        # 强制归零
        status["current_streak"] = 0
        status["shield_status"] = 0
        status["shield_level"] = 0
        # 扣分（原则性错误惩罚更重）
        penalty = min(status["total_score"], 50)
        status["total_score"] = max(0, status["total_score"] - penalty)
        self._save_status(status)
        
        self._log_event(f"原则性错误 [{reason}]，连击 {old_streak}→0，扣分 {penalty}")
        
        return {
            "blocked": False,
            "streak_preserved": False,
            "streak_lost": old_streak,
            "penalty": penalty,
            "message": f"原则性错误 [{reason}]，无护盾保护，连击归零，扣分 {penalty}",
        }
    
    def _trigger_meltdown(
        self,
        status: Dict,
        task_type: str,
        quality_score: float,
        bonus: float
    ) -> Dict[str, Any]:
        """触发熔断：超过60小时无交互"""
        old_streak = status["current_streak"]
        
        status["current_streak"] = 0
        status["shield_status"] = 0
        status["shield_level"] = 0
        status["melted"] = True
        status["last_meltdown_time"] = now()
        self._save_status(status)
        
        self._log_event(f"熔断触发：{old_streak}连击归零，熔断时长>60h")
        
        return {
            "success": False,
            "reason": "meltdown",
            "melted": True,
            "streak_before": old_streak,
            "streak_after": 0,
            "elapsed_hours": hours_since(status["last_active_time"]),
            "message": f"熔断：超过60小时无交互，连击归零",
        }
    
    def on_user_silence(self) -> Dict[str, Any]:
        """
        检测到用户沉默时调用（用于判断用户是否"消失"）
        应当在每次对话前/定时任务中调用
        """
        status = self._load_status()
        elapsed_hours = hours_since(status["last_active_time"])
        
        # 刷新熵增系数
        k_entropy = calc_k_entropy(elapsed_hours)
        status["k_entropy"] = k_entropy
        
        if 1 <= elapsed_hours <= 24:
            status["frozen"] = True
            self._save_status(status)
            return {
                "mode": "frozen",
                "streak_preserved": True,
                "shield_frozen": True,
                "medals_frozen": True,
                "elapsed_hours": round(elapsed_hours, 1),
                "message": "沉默1-24h：连击冻结保留",
            }
        elif elapsed_hours > 24:
            # 超过24小时，护盾破碎但连击保留
            if status["shield_status"] == 1:
                status["shield_status"] = 0
                status["frozen"] = True
                self._save_status(status)
                return {
                    "mode": "meltdown_risk",
                    "streak_preserved": False,
                    "shield_broken": True,
                    "elapsed_hours": round(elapsed_hours, 1),
                    "message": f"沉默超过24h，护盾破碎。连击保留（{status['current_streak']}），超过60h将归零",
                }
        
        self._save_status(status)
        return {
            "mode": "active",
            "streak_preserved": True,
            "elapsed_hours": round(elapsed_hours, 1),
        }
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前连击状态"""
        status = self._load_status()
        elapsed_hours = hours_since(status["last_active_time"])
        k_entropy = calc_k_entropy(elapsed_hours)
        streak = status["current_streak"]
        s_info = calc_s_multiplier(streak)
        shield_info = calc_shield_level(streak)
        
        # 判断模式
        if status.get("melted"):
            mode = "熔断（已重新激活）"
        elif status.get("frozen"):
            mode = "冻结（沉默1-24h）"
        elif k_entropy == 0:
            mode = "衰退（熵增耗尽）"
        elif k_entropy < 1.0:
            mode = f"冷却（K={k_entropy:.2f}）"
        else:
            mode = "活跃"
        
        return {
            "user_id": self.user_id,
            "current_streak": streak,
            "phase": s_info["phase"],
            "s_multiplier": s_info["s_multiplier"],
            "k_entropy": round(k_entropy, 2),
            "shield_level": shield_info["name"],
            "shield_status": "完好" if status["shield_status"] == 1 else "已破碎",
            "earned_medals": status["earned_medals"],
            "total_tasks_completed": status["total_tasks_completed"],
            "total_score": status["total_score"],
            "mode": mode,
            "elapsed_hours": round(elapsed_hours, 1),
            "last_active_time": status["last_active_time"],
        }
    
    def get_full_report(self) -> Dict[str, Any]:
        """获取完整状态报告（含所有字段）"""
        return self._load_status()
    
    def _log_event(self, message: str) -> None:
        """记录事件到防御日志"""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        log_entry = f"\n[{timestamp}] [STREAK] {message}"
        
        # 追加到日志文件
        log_path = Config.DEFENSE_LOG_FILE
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)


# ============================================================
# 便捷函数（模块级API）
# ============================================================

# 全局单例（延迟初始化）
_calculator: Optional[StreakCalculator] = None

def get_calculator(user_id: str = "default_user") -> StreakCalculator:
    """获取连击计算器单例"""
    global _calculator
    if _calculator is None:
        _calculator = StreakCalculator(user_id)
    return _calculator

def task_completed(
    task_type: str = "general",
    quality_score: float = 1.0,
    bonus: float = 1.0
) -> Dict[str, Any]:
    """快捷函数：任务完成"""
    return get_calculator().on_task_completed(task_type, quality_score, bonus)

def interaction() -> Dict[str, Any]:
    """快捷函数：任意交互"""
    return get_calculator().on_interaction()

def negative_feedback(reason: str = "轻微负面") -> Dict[str, Any]:
    """快捷函数：遭遇负面反馈"""
    return get_calculator().on_mild_negative(reason)

def principle_error(reason: str = "原则性错误") -> Dict[str, Any]:
    """快捷函数：原则性错误"""
    return get_calculator().on_principle_error(reason)

def silence_check() -> Dict[str, Any]:
    """快捷函数：沉默检测"""
    return get_calculator().on_user_silence()

def status() -> Dict[str, Any]:
    """快捷函数：查询状态"""
    return get_calculator().get_status()


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("TU-8 Streak Calculator v1.0")
    print("=" * 50)
    
    calc = get_calculator()
    
    # Current status
    s = calc.get_status()
    print(f"\n[STATUS]")
    print(f"  Streak: {s['current_streak']} | Phase: {s['phase']}")
    print(f"  Shield: {s['shield_level']} ({s['shield_status']})")
    print(f"  Score: {s['total_score']} | Tasks: {s['total_tasks_completed']}")
    print(f"  Medals: {', '.join(s['earned_medals']) or 'None'}")
    print(f"  Mode: {s['mode']}")
    print(f"  Hours since last: {s['elapsed_hours']}h")
    
    # Simulate task completion
    print(f"\n[TEST] Simulating task completion (quality=0.9):")
    result = calc.on_task_completed(task_type="test", quality_score=0.9)
    for k, v in result.items():
        print(f"  {k}: {v}")
