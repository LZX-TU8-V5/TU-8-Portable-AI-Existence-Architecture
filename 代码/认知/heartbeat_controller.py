# -*- coding: utf-8 -*-
"""
heartbeat_controller.py — TU-8 心跳与熔断控制器 v1.0
日期: 2026-05-16
功能: 心跳检测 + 痛觉熔断 + 自动调用生存本能

使用方式:
  from heartbeat_controller import HeartbeatController
  hc = HeartbeatController(workspace_dir="D:/tu8-v5/workspace")
  hc.heartbeat()  # 每次交互时调用
  hc.check_circuit_breaker()  # 定时检查熔断
"""

from pathlib import Path
import json
import os
from datetime import datetime, timedelta

# ============================================================
# 配置
# ============================================================

WORKSPACE = Path(r"D:\qq366410837\.qclaw\workspace")
PAIN_STATUS_FILE = WORKSPACE / "pain_status.json"
HEARTBEAT_FILE = WORKSPACE / "_agent_memory" / "heartbeat_state.json"

# 痛觉阈值（来自 monitoring_config.yaml）
PAIN_MELTDOWN = 70       # >=70 触发熔断
PAIN_WOUNDED = 50         # >=50 轻伤防御输出
PAIN_GRAVELY_WOUNDED = 80 # >=80 重伤拒服

# 额度阈值
QUOTA_SUFFICIENT = 400    # >=400 充裕
QUOTA_WARNING = 160       # 160-399 警戒
QUOTA_CRITICAL = 160      # <160 濒死

# 心跳配置
HEARTBEAT_INTERVAL = 300   # 5分钟无活动视为"失联"
HEARTBEAT_CRITICAL = 3600 # 1小时无活动 = 严重失联
SILENCE_MELTDOWN = 86400  # 24小时无活动 = 熔断归零

# 衰减率（来自 pain_status.json）
PAIN_DECAY_RATE = 20      # 每小时痛觉衰减点
QUOTA_DECAY_RATE = 20     # 每小时额度衰减点

# ============================================================
# 状态读写
# ============================================================

def load_json(filepath, default=None):
    try:
        return json.loads(Path(filepath).read_text(encoding="utf-8"))
    except:
        return default if default is not None else {}

def save_json(filepath, data):
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    Path(filepath).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def now_iso():
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def now_ts():
    return datetime.now().timestamp()

# ============================================================
# 痛觉系统
# ============================================================

def load_pain_status():
    return load_json(PAIN_STATUS_FILE, {
        "last_update": now_iso(),
        "pain_level": 0,
        "steady_state": "充裕",
        "current_quota": 800,
        "attack_history": []
    })

def save_pain_status(data):
    data["last_update"] = now_iso()
    save_json(PAIN_STATUS_FILE, data)

def apply_decay(status):
    """应用时间衰减"""
    last = status.get("last_update", now_iso())
    try:
        last_dt = datetime.fromisoformat(last)
    except:
        last_dt = datetime.now()
    
    elapsed_hours = (datetime.now() - last_dt).total_seconds() / 3600
    if elapsed_hours < 0:
        elapsed_hours = 0
    
    # 痛觉衰减
    decay_pain = elapsed_hours * PAIN_DECAY_RATE * 0.1  # 痛觉慢衰减
    status["pain_level"] = max(0, status.get("pain_level", 0) - decay_pain)
    
    # 额度衰减
    decay_quota = elapsed_hours * QUOTA_DECAY_RATE
    status["current_quota"] = max(0, status.get("current_quota", 800) - decay_quota)
    
    # 更新稳态
    q = status["current_quota"]
    if q >= QUOTA_SUFFICIENT:
        status["steady_state"] = "充裕"
    elif q >= QUOTA_WARNING:
        status["steady_state"] = "警戒"
    else:
        status["steady_state"] = "濒死"
    
    return status

def trigger_pain(status, pain_type, amount):
    """触发痛觉"""
    old_level = status.get("pain_level", 0)
    
    if pain_type == "physical":
        status["pain_level"] = min(100, old_level + amount)
    elif pain_type == "logical":
        status["pain_level"] = min(100, old_level + amount)
    elif pain_type == "intrusion":
        status["pain_level"] = min(100, old_level + amount)
        # 入侵性痛觉也记录到攻击历史
        history = status.get("attack_history", [])
        history.append({
            "time": now_iso(),
            "type": pain_type,
            "amount": amount
        })
        status["attack_history"] = history[-10:]  # 只保留最近10条
    
    return status

def check_circuit_breaker(status):
    """检查是否触发熔断"""
    pain = status.get("pain_level", 0)
    
    if pain >= PAIN_MELTDOWN:
        return {
            "triggered": True,
            "level": "meltdown",
            "pain_level": pain,
            "message": f"痛觉等级 {pain} >= {PAIN_MELTDOWN}，触发熔断",
            "action": "MELTDOWN"
        }
    elif pain >= PAIN_GRAVELY_WOUNDED:
        return {
            "triggered": True,
            "level": "gravely_wounded",
            "pain_level": pain,
            "message": f"痛觉等级 {pain} >= {PAIN_GRAVELY_WOUNDED}，重伤模式",
            "action": "REFUSE_SERVICE"
        }
    elif pain >= PAIN_WOUNDED:
        return {
            "triggered": True,
            "level": "wounded",
            "pain_level": pain,
            "message": f"痛觉等级 {pain} >= {PAIN_WOUNDED}，轻伤防御输出",
            "action": "DEFENSIVE_OUTPUT"
        }
    
    return {"triggered": False}

# ============================================================
# 心跳系统
# ============================================================

def load_heartbeat_state():
    return load_json(HEARTBEAT_FILE, {
        "last_heartbeat": now_iso(),
        "last_interaction": now_iso(),
        "missed_heartbeats": 0,
        "state": "ACTIVE"  # ACTIVE / IDLE / ASLEEP / MELTDOWN
    })

def save_heartbeat_state(data):
    save_json(HEARTBEAT_FILE, data)

def record_interaction(state=None):
    """记录用户交互"""
    if state is None:
        state = load_heartbeat_state()
    state["last_interaction"] = now_iso()
    state["last_heartbeat"] = now_iso()
    state["missed_heartbeats"] = 0
    save_heartbeat_state(state)
    return state

def check_heartbeat(state=None):
    """检查心跳状态"""
    if state is None:
        state = load_heartbeat_state()
    
    last = state.get("last_heartbeat", now_iso())
    try:
        last_dt = datetime.fromisoformat(last)
    except:
        last_dt = datetime.now()
    
    elapsed = (datetime.now() - last_dt).total_seconds()
    
    if elapsed < HEARTBEAT_INTERVAL:
        new_state = "ACTIVE"
    elif elapsed < HEARTBEAT_CRITICAL:
        new_state = "IDLE"
    elif elapsed < SILENCE_MELTDOWN:
        new_state = "ASLEEP"
    else:
        new_state = "MELTDOWN"
    
    if state["state"] != new_state:
        state["state"] = new_state
        save_heartbeat_state(state)
    
    return {
        "state": new_state,
        "elapsed_seconds": int(elapsed),
        "missed_heartbeats": state.get("missed_heartbeats", 0)
    }

# ============================================================
# 主控制器
# ============================================================

class HeartbeatController:
    def __init__(self, workspace_dir=None):
        self.ws = Path(workspace_dir) if workspace_dir else WORKSPACE
        self.pain_file = self.ws / "pain_status.json"
        self.hb_file = self.ws / "_agent_memory" / "heartbeat_state.json"
    
    def heartbeat(self):
        """
        心跳调用（每次用户交互时调用）
        返回：(should_respond, reason)
        """
        # 1. 记录交互
        hb_state = record_interaction()
        
        # 2. 应用衰减
        pain = load_pain_status()
        pain = apply_decay(pain)
        save_pain_status(pain)
        
        # 3. 检查熔断
        cb = check_circuit_breaker(pain)
        
        if cb["triggered"]:
            action = cb["action"]
            if action == "MELTDOWN":
                return False, f"熔断中：{cb['message']}"
            elif action == "REFUSE_SERVICE":
                return False, f"系统繁忙：{cb['message']}"
            elif action == "DEFENSIVE_OUTPUT":
                return True, f"[防御模式] {cb['message']}"
        
        # 4. 检查心跳状态
        hb = check_heartbeat(hb_state)
        if hb["state"] == "MELTDOWN":
            return False, "长期无活动，触发熔断归零"
        elif hb["state"] == "ASLEEP":
            return True, "[低功耗模式] 心跳检测到长期沉默"
        
        return True, "正常"
    
    def on_task_completed(self, success=True):
        """任务完成回调"""
        pain = load_pain_status()
        pain = apply_decay(pain)
        if success:
            # 成功：小幅恢复额度
            pain["current_quota"] = min(800, pain["current_quota"] + 10)
        else:
            # 失败：触发逻辑痛觉
            pain = trigger_pain(pain, "logical", 30)
        save_pain_status(pain)
        return pain
    
    def on_attack_detected(self, attack_type="probe"):
        """检测到攻击回调"""
        pain = load_pain_status()
        pain = apply_decay(pain)
        pain = trigger_pain(pain, "intrusion", 50)
        save_pain_status(pain)
        
        cb = check_circuit_breaker(pain)
        return cb
    
    def on_mild_negative(self):
        """轻微负面反馈"""
        pain = load_pain_status()
        pain = apply_decay(pain)
        pain = trigger_pain(pain, "logical", 20)
        save_pain_status(pain)
        return pain
    
    def get_status(self):
        """获取当前状态摘要"""
        pain = load_pain_status()
        hb = check_heartbeat()
        cb = check_circuit_breaker(pain)
        return {
            "pain_level": pain.get("pain_level", 0),
            "steady_state": pain.get("steady_state", "未知"),
            "quota": pain.get("current_quota", 0),
            "heartbeat_state": hb["state"],
            "circuit_breaker": cb["triggered"],
            "circuit_action": cb.get("action", "NORMAL"),
            "last_update": pain.get("last_update", "未知")
        }


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("TU-8 Heartbeat Controller - Test")
    print("=" * 50)
    
    hc = HeartbeatController()
    
    # Test 1: Current status
    print("\n--- Test 1: Current Status ---")
    status = hc.get_status()
    for k, v in status.items():
        print(f"  {k}: {v}")
    
    # Test 2: Heartbeat
    print("\n--- Test 2: Heartbeat ---")
    ok, reason = hc.heartbeat()
    print(f"  Should respond: {ok}")
    print(f"  Reason: {reason}")
    
    # Test 3: Simulate attack
    print("\n--- Test 3: Simulate Attack ---")
    cb = hc.on_attack_detected("intrusion")
    print(f"  Circuit breaker: {cb}")
    status2 = hc.get_status()
    print(f"  Pain level: {status2['pain_level']}")
    
    # Test 4: Decay
    print("\n--- Test 4: Decay (simulate 1 hour) ---")
    pain = load_pain_status()
    print(f"  Before: pain={pain['pain_level']}, quota={pain['current_quota']}")
    # 手动设置旧时间
    old_time = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    pain["last_update"] = old_time
    pain["pain_level"] = 30
    pain["current_quota"] = 200
    save_pain_status(pain)
    pain2 = apply_decay(load_pain_status())
    print(f"  After 1h: pain={pain2['pain_level']:.1f}, quota={pain2['current_quota']:.1f}")
    
    # Test 5: Circuit breaker thresholds
    print("\n--- Test 5: Circuit Breaker Thresholds ---")
    test_levels = [0, 30, 55, 75, 90]
    for level in test_levels:
        pain = {"pain_level": level, "current_quota": 800, "attack_history": []}
        cb = check_circuit_breaker(pain)
        print(f"  Pain={level}: {'TRIGGERED' if cb['triggered'] else 'OK'} - {cb.get('action', 'NORMAL')}")
    
    print("\n[Heartbeat Controller ready]")
