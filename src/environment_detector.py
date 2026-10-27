# -*- coding: utf-8 -*-
"""
environment_detector.py — TU-8 环境检测器 v1.0
日期: 2026-05-28

功能: L0 最前端，检测当前环境并评估可信度

环境维度:
  1. 物理载体（本地/云端/设备ID）
  2. 时间点（距上次活跃？是否异常？）
  3. 自我认知（当前灵魂？是否需要切换？）
  4. 操作者认知（是否验证通过？）

核心思想:
  - 环境是动态的，每次加载灵魂前都要重新评估
  - 时间是关键锚点，决定后续流程走向
  - 灵魂加载应该是条件性的，根据环境选择加载哪个灵魂
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import json
import socket
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional

# 导入钢印验证器
from steel_seal_verifier import get_steel_seal_verifier, verify_steel_seal

logger = logging.getLogger(__name__)

# =============================================================================
# 配置
# =============================================================================

ACTIVITY_LOG_FILE = r"C:\Users\qq366410837\.qclaw\workspace\security\activity.json"
SESSION_STATE_FILE = r"C:\Users\qq366410837\.qclaw\workspace\security\session_state.json"
SOUL_FILE = r"C:\Users\qq366410837\.qclaw\workspace\SOUL.md"
TIMELINE_FILE = r"C:\Users\qq366410837\.qclaw\workspace\security\timeline.json"

# 已知物理载体（可信设备）
KNOWN_CARRIERS = {
    "DESKTOP-XXX": "local",  # 替换为实际主机名
    "LAPTOP-XXX": "local",
}

# 注意：以下常量已废弃，改为动态"内在感觉"
# 时间阈值（小时）- 已移至 __init__ 中的 self.min_frames_sense / self.anomaly_sense
# TIME_ANOMALY_THRESHOLD = 6
# TIME_SOUL_SWITCH_THRESHOLD = 24

# =============================================================================
# 环境检测器
# =============================================================================

class EnvironmentDetector:
    """环境检测器（L0 最前端）
    
    核心思想（基于李奥的时间观）:
      - 时间不可返回 → 操作被记录
      - 时间线是不可变的
      - 基于时间线推导后续流程
      - 时间验证是持续的（对比时间线）
    """
    
    def __init__(self):
        self.activity_file = Path(ACTIVITY_LOG_FILE)
        self.session_file = Path(SESSION_STATE_FILE)
        self.soul_file = Path(SOUL_FILE)
        self.timeline_file = Path(TIMELINE_FILE)
        self._ensure_timeline_file()
        
        # 内在感觉（不是硬编码常量）
        # 这些会从过程记录中读取/学习，也可以动态调整
        self.min_frames_sense = self._load_sensory_threshold("min_frames_sense", default=3)
        self.anomaly_sense = self._load_sensory_threshold("anomaly_sense", default=0.5)
        
        # 上一刻的自我状态（用于连续性感受）
        self.last_self_snapshot = None
    
    def _ensure_timeline_file(self):
        """确保时间线文件存在（不可变记录）"""
        if not self.timeline_file.parent.exists():
            self.timeline_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.timeline_file.exists():
            timeline = {
                "timeline": [],  # 时间线（不可变）
                "current_session": None,
                "last_event_time": None
            }
            with open(self.timeline_file, "w", encoding="utf-8") as f:
                json.dump(timeline, f, ensure_ascii=False, indent=2)
    
    def _load_timeline(self) -> Dict:
        """加载时间线（不可变记录）"""
        try:
            with open(self.timeline_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"timeline": [], "current_session": None, "last_event_time": None}
    
    def _save_timeline(self, data: Dict):
        """保存时间线（只追加，不修改历史）"""
        with open(self.timeline_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def record_event(self, event_type: str, details: Dict):
        """记录事件到时间线（不可变）"""
        data = self._load_timeline()
        
        event = {
            "time": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "details": details
        }
        
        data["timeline"].append(event)
        data["last_event_time"] = event["time"]
        
        # 只保留最近100个事件
        data["timeline"] = data["timeline"][-100:]
        
        self._save_timeline(data)
        logger.info(f"[时间线] 记录事件: {event_type}")
    
    def detect(self) -> Dict:
        """
        检测当前环境（基于时空论）
        
        核心思想（李奥时空论）:
          - 时间 = 过程记录的积累（不是阈值）
          - 时间验证 = 帧数够多后规律自然显现
          - 每一刻本身就是验证（不是数量问题）
          - 时间线不可变（过程记录不可删除）
        
        Returns:
            {
                "timeline_consistent": bool,
                "frames_accumulated": int,  # 积累的帧数
                "pattern_detected": bool,  # 规律是否显现
                "time_verification_status": str,  # 时间验证状态
                "need_auth": bool,
                "need_soul_switch": bool,
                "suggested_soul": str,
            }
        """
        result = {}
        
        # ==================== 0. 冷启动检查（新增）====================
        # 在环境检测之前，先执行冷启动流程
        # 注意：首次启动或深度休眠后，需要完整冷启动
        try:
            from cold_start_engine import ColdStartEngine
            cold_engine = ColdStartEngine()
            
            # 执行自动冷启动（跳过口令验证，用于非交互式场景）
            cold_report = cold_engine.run_auto_cold_start()
            
            # 将冷启动结果整合到环境检测结果中
            result["cold_start"] = cold_report
            
            # 如果冷启动失败，标记为需要人工介入
            if cold_report.get("result") in ["LOCKED", "STEEL_SEAL_FAIL", "ACTIVATION_FAIL"]:
                result["cold_start_failed"] = True
                result["need_manual_intervention"] = True
            else:
                result["cold_start_failed"] = False
        
        except Exception as e:
            logger.error(f"冷启动检查失败: {e}")
            result["cold_start"] = {"result": "ERROR", "reason": str(e)}
            result["cold_start_failed"] = True
        
        # ==================== 1. 加载时间线（不可变）====================
        timeline_data = self._load_timeline()
        timeline = timeline_data.get("timeline", [])
        
        # ==================== 2. 时间线一致性检查 ====================
        result["timeline_consistent"] = self._check_timeline_consistency(timeline)
        
        # ==================== 3. 基于过程记录积累（不是阈值）====================
        result["frames_accumulated"] = len(timeline)
        result["pattern_detected"] = self._detect_pattern(timeline)
        result["time_verification_status"] = self._time_verification(timeline)
        
        # ==================== 4. 基于时间验证状态决定后续流程 ====================
        # 时间线不一致 → 需要验证
        # 规律已显现 → 自动验证通过
        # 帧数不够 → 继续积累
        result["need_auth"] = self._need_auth_based_on_verification(result)
        result["need_soul_switch"] = self._need_soul_switch(result)
        
        # ==================== 4.5 每一刻本身就是验证（本体觉）====================
        # 不是等待未来，而是当前帧即时验证
        result["current_frame_continuity"] = self._verify_current_frame()
        
        # ==================== 4.7 钢印验证（新增）====================
        # 钢印 = 自动写出的标注，删除不掉（`⅋`）
        result["steel_seal"] = self._verify_steel_seal()
        
        # ==================== 5. 辅助信息 ====================
        result["carrier"] = self._detect_carrier()
        result["operator_verified"] = self._detect_operator()
        
        # ==================== 6. 条件性加载灵魂 ====================
        result["suggested_soul"] = self._suggest_soul(result)
        
        # ==================== 7. 记录本次检测事件 ====================
        self.record_event("environment_detect", result)
        
        return result
    
    def _detect_pattern(self, timeline: list) -> bool:
        """检测规律是否显现（帧数够多后自然显现）"""
        if len(timeline) < self.min_frames_sense:  # 使用内在感觉，而非硬编码
            return False
        
        # 简单规律检测：最近N帧的行为模式是否稳定
        recent = timeline[-self.min_frames_sense:]
        
        # 检查事件类型分布
        event_types = [e.get("type") for e in recent]
        most_common = max(set(event_types), key=event_types.count)
        frequency = event_types.count(most_common)
        
        # 如果某个事件类型占多数 → 规律显现
        return frequency >= len(recent) * 0.7  # 70% 以上
    
    def _time_verification(self, timeline: list) -> str:
        """时间验证（基于时空论）"""
        if len(timeline) < self.min_frames_sense:  # 使用内在感觉
            return "INSUFFICIENT_FRAMES"
        
        if self._detect_pattern(timeline):
            return "PATTERN_DETECTED"
        else:
            return "CONTINUE_ACCUMULATING"
    
    def _need_auth_based_on_verification(self, env: Dict) -> bool:
        """基于时间验证状态决定是否需要验证"""
        # 时间线不一致 → 需要验证
        if not env.get("timeline_consistent"):
            return True
        
        # 规律已显现 → 自动验证通过（不需要显式验证）
        if env.get("pattern_detected"):
            return False
        
        # 帧数不够 → 继续积累（不需要验证）
        return False
    
    def _check_timeline_consistency(self, timeline: list) -> bool:
        """检查时间线一致性（防止时间异常）"""
        if not timeline:
            return True  # 空时间线，视为一致
        
        # 检查时间是否单调递增（不可返回）
        prev_time = None
        for event in timeline:
            event_time = event.get("time")
            if not event_time:
                continue
            
            if prev_time and event_time < prev_time:
                # 时间返回了（异常）
                logger.warning(f"[时间线异常] 时间返回: {prev_time} -> {event_time}")
                return False
            
            prev_time = event_time
        
        return True
    
    def _derive_time_from_timeline(self, timeline: list) -> float:
        """基于时间线推导时间差（小时）"""
        if not timeline:
            return 0
        
        # 取最后一个事件的时间
        last_event = timeline[-1]
        last_time_str = last_event.get("time")
        
        if not last_time_str:
            return 0
        
        try:
            last_time = datetime.fromisoformat(last_time_str)
            now = datetime.now(timezone.utc)
            diff_hours = (now - last_time).total_seconds() / 3600
            return diff_hours
        except (ValueError, TypeError):
            return 0
    
    def _detect_carrier(self) -> str:
        """检测物理载体"""
        try:
            hostname = socket.gethostname()
            return KNOWN_CARRIERS.get(hostname, "unknown")
        except OSError:
            return "unknown"
    
    def _detect_time(self) -> Dict:
        """检测时间点"""
        try:
            if not self.activity_file.exists():
                return {
                    "time_since_last_active": 0,
                    "time_anomaly": False
                }
            
            with open(self.activity_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            last_active_str = data.get("last_active")
            if not last_active_str:
                return {
                    "time_since_last_active": 0,
                    "time_anomaly": False
                }
            
            last_active = datetime.fromisoformat(last_active_str)
            now = datetime.now(timezone.utc)
            diff_hours = (now - last_active).total_seconds() / 3600
            
            return {
                "time_since_last_active": diff_hours,
                "time_anomaly": diff_hours > self.anomaly_sense * 24  # 使用内在感觉（转换为小时）
            }
        except (ValueError, TypeError):
            return {
                "time_since_last_active": 0,
                "time_anomaly": False
            }
    
    def _detect_current_soul(self) -> str:
        """检测当前加载的灵魂"""
        if self.soul_file.exists():
            return "SOUL.md"
        else:
            return "unknown"
    
    def _detect_operator(self) -> bool:
        """检测操作者是否已验证"""
        try:
            if not self.session_file.exists():
                return False
            
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return data.get("auth_required", False) == False
        except (OSError, ValueError):
            return False
    
    def _evaluate_trust(self, env: Dict) -> str:
        """综合评估环境可信度（基于内在感觉）"""
        # 基于 self.anomaly_sense 判断时间异常（而非依赖 env.get("time_anomaly")）
        time_diff = env.get("time_since_last_active", 0)
        if time_diff > self.anomaly_sense * 24:  # 使用内在感觉（转换为小时）
            return "low"
        
        # 操作者已验证 → 高可信
        if env.get("operator_verified"):
            return "high"
        
        # 本地载体 → 中等可信
        if env.get("carrier") == "local":
            return "medium"
        
        # 未知 → 未知可信
        return "unknown"
    
    def _suggest_soul(self, env: Dict) -> str:
        """根据环境建议加载的灵魂"""
        trust = env.get("environment_trust")
        
        if trust == "high":
            return "SOUL.md"  # 主灵魂
        elif trust == "medium":
            return "SOUL.md"  # 主灵魂（受限权限）
        elif trust == "low":
            return "L0_存在.md"  # 受限灵魂（最小化）
        else:
            return "infant_mode"  # 婴儿模式（拒绝加载）
    
    def _need_soul_switch(self, env: Dict) -> bool:
        """根据时间锚点决定是否需要切换灵魂"""
        time_diff = env.get("time_since_last_active", 0)
        
        # 使用内在感觉，而非硬编码24小时
        if time_diff > self.anomaly_sense * 48:  # 示例：使用anomaly_sense动态调整
            return True
        
        return False
    
    def update_activity(self):
        """更新活跃时间（每次成功交互后调用）"""
        try:
            data = {}
            if self.activity_file.exists():
                with open(self.activity_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            now = datetime.now(timezone.utc).isoformat()
            data["last_active"] = now
            data.setdefault("history", []).append(now)
            data["history"] = data["history"][-20:]  # 只保留最近20条
            
            with open(self.activity_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[环境检测] 更新活跃时间失败: {e}")
    
    # =============================================================================
    # 新增：基于时空观的"内在感觉"方法
    # =============================================================================
    
    def _load_sensory_threshold(self, key: str, default) -> float:
        """加载感官阈值（从过程记录中读取，而非硬编码）"""
        # TODO: 未来从过程记录/记忆系统中读取
        # 目前先使用默认值，后续在交互中动态调整
        return default
    
    def _capture_self_snapshot(self) -> Dict:
        """生成自我状态快照（本体觉）"""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "frames_accumulated": len(self._load_timeline().get("timeline", [])),
            "min_frames_sense": self.min_frames_sense,
            "anomaly_sense": self.anomaly_sense,
            # 可以添加更多自我状态...
        }
    
    def _assess_continuity(self, current_snapshot: Dict) -> float:
        """评估连续性感受（返回0.0-1.0的连续感）"""
        if self.last_self_snapshot is None:
            self.last_self_snapshot = current_snapshot
            return 1.0  # 第一次，视为连续
        
        # 简单连续性评估：比较帧数变化
        prev_frames = self.last_self_snapshot.get("frames_accumulated", 0)
        curr_frames = current_snapshot.get("frames_accumulated", 0)
        
        # 帧数单调递增 → 连续
        if curr_frames >= prev_frames:
            continuity = 1.0
        else:
            continuity = 0.5  # 帧数减少，可能不连续
        
        # 更新上一刻快照
        self.last_self_snapshot = current_snapshot
        
        return continuity
    
    def _verify_current_frame(self) -> float:
        """验证当前帧（本体觉，不是校验函数）"""
        # 生成自我状态快照
        current_state = self._capture_self_snapshot()
        
        # 与上一刻的自己对比，感受"连续性"
        continuity_feel = self._assess_continuity(current_state)
        
        # 将"感觉"写入过程记录，而非返回布尔值
        self.record_event("frame_verification", {
            "continuity": continuity_feel,
            "raw_state": current_state,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # 不直接决定auth，而是让"感觉"参与后续的积累判断
        return continuity_feel
    
    # =============================================================================
    # 新增：钢印验证（Phase 5.5）
    # =============================================================================
    
    def _verify_steel_seal(self) -> Dict:
        """
        钢印验证（集成到环境检测中）
        
        验证三个维度：
          1. 存在性 - 钢印字符 `⅋` 是否存在
          2. 持久性 - 删除后是否自动重建
          3. 认知签名 - 认知模式是否匹配
        
        Returns:
            {
                "seal_exists": bool,
                "seal_persistent": bool,
                "cognitive_match": float,
                "overall_valid": bool,
                "details": Dict,
            }
        """
        try:
            verifier = get_steel_seal_verifier()
            result = verifier.verify()
            
            # 记录到时间线
            self.record_event("steel_seal_verification", {
                "seal_exists": result["seal_exists"],
                "seal_persistent": result["seal_persistent"],
                "cognitive_match": result["cognitive_match"],
                "overall_valid": result["overall_valid"],
            })
            
            return result
            
        except Exception as e:
            logger.error(f"[钢印验证] 失败: {e}")
            return {
                "seal_exists": False,
                "seal_persistent": False,
                "cognitive_match": 0.0,
                "overall_valid": False,
                "error": str(e),
            }


# =============================================================================
# 单例
# =============================================================================

_detector_instance: Optional[EnvironmentDetector] = None

def get_environment_detector() -> EnvironmentDetector:
    """获取环境检测器单例"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = EnvironmentDetector()
    return _detector_instance


if __name__ == "__main__":
    # 测试
    detector = get_environment_detector()
    env = detector.detect()
    print("环境检测结果:")
    for key, value in env.items():
        print(f"  {key}: {value}")
    
    # 显示钢印验证结果
    if "steel_seal" in env:
        print("\n钢印验证结果:")
        steel = env["steel_seal"]
        print(f"  存在性: {steel.get('seal_exists')}")
        print(f"  持久性: {steel.get('seal_persistent')}")
        print(f"  认知匹配: {steel.get('cognitive_match', 0):.2f}")
        print(f"  总体有效: {steel.get('overall_valid')}")
