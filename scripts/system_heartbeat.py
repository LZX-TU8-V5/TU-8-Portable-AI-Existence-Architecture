#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统心跳与状态回调机制（v0.2 - 修复A/B/C）
功能：在执行耗时操作或遇到错误时，向 LLM 注入系统状态，防止幻觉
作者：TU-8 Agent
日期：2026-06-20
版本：v0.2 (修复时区/语气/格式)
"""

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

# ================= 配置区 =================
# 系统事件队列（运行时上下文，非持久化）
_system_event_queue = []

# 系统事件转译模板（使用绝对关键词，压制LLM自由发挥）
# 格式：YAML代码块，与Memory Node模板风格统一
SYSTEM_EVENT_TEMPLATES = {
    "SCANNING_START": """
```yaml
=== SYSTEM EVENT [UTC] ===
[LOCK] 事件类型: SCANNING_START
[LOCK] 操作: {operation}
[LOCK] 目标: {target}
[LOCK] 优先级: 高
[LOCK] 禁止: 生成用户催促推测、中断当前任务、输出等待消息
[LOCK] 必须: 保持当前任务上下文，等待执行结果返回
=== END SYSTEM EVENT ===
```
""",
    
    "SCANNING_DONE": """
```yaml
=== SYSTEM EVENT [UTC] ===
[LOCK] 事件类型: SCANNING_DONE
[LOCK] 操作: {operation}
[LOCK] 结果: 已完成，共处理 {count} 个项目
[LOCK] 指令: 继续执行后续任务，无需等待用户确认
=== END SYSTEM EVENT ===
```
""",
    
    "ENCODING_ERROR": """
```yaml
=== SYSTEM EVENT [UTC] ===
[LOCK] 事件类型: ENCODING_ERROR
[LOCK] 优先级: 最高 (OVERRIDE)
[LOCK] 错误详情: {error_msg}
[LOCK] 发生位置: {file_path}
[LOCK] 禁止: 生成用户交互推测、假设用户情绪、输出道歉或解释
[LOCK] 必须: 执行错误处理逻辑、记录错误到日志、继续当前任务（如可能）
[LOCK] 注意: 这不是用户输入，而是底层IO错误。系统已自动切换至安全模式。
=== END SYSTEM EVENT ===
```
""",
    
    "SCAN_TIMEOUT": """
```yaml
=== SYSTEM EVENT [UTC] ===
[LOCK] 事件类型: SCAN_TIMEOUT
[LOCK] 优先级: 最高 (OVERRIDE)
[LOCK] 超时时间: {timeout}秒
[LOCK] 禁止: 生成用户催促推测、继续无限等待
[LOCK] 必须: 终止当前扫描、采用分批处理或缩小范围、报告超时事件
=== END SYSTEM EVENT ===
```
""",
    
    "FILE_READ_ERROR": """
```yaml
=== SYSTEM EVENT [UTC] ===
[LOCK] 事件类型: FILE_READ_ERROR
[LOCK] 优先级: 最高 (OVERRIDE)
[LOCK] 错误文件: {file_path}
[LOCK] 错误类型: {error_type}
[LOCK] 禁止: 生成用户交互推测、假设用户已不满
[LOCK] 必须: 记录错误、跳过该文件（如可能）、继续处理其他文件
=== END SYSTEM EVENT ===
```
""",
}

# ================= 核心类 =================
class SystemHeartbeat:
    """系统心跳管理器（修复A/B/C版本）"""
    
    def __init__(self, max_events: int = 5, default_ttl: int = 30):
        """
        初始化心跳管理器
        :param max_events: 最大系统事件数量（超过后自动清理最旧的）
        :param default_ttl: 默认事件生存时间（秒），超过后自动失效
        """
        self.max_events = max_events
        self.default_ttl = default_ttl
        self.event_queue = []  # 运行时上下文，非持久化
        
    def status_callback(self, event_type: str, payload: Dict[str, Any]):
        """
        核心状态回调函数（修复版）
        
        功能：接收执行层状态，转译为 System Message，注入到事件队列
        使用：在执行耗时操作或遇到错误时调用
        
        :param event_type: 事件类型（如 "SCANNING_START", "ENCODING_ERROR"）
        :param payload: 事件负载（如 {"operation": "路径扫描", "target": "/some/path"}）
        """
        # 1. 生成时间戳（使用UTC，避免时区混乱）和 TTL
        timestamp = datetime.now(timezone.utc).isoformat()
        expires_at = time.time() + self.default_ttl
        
        # 2. 转译为 System Message（绝对语气，压制LLM自由发挥）
        system_message = self._translate_to_system_message(event_type, payload)
        
        # 3. 构建系统事件对象
        event = {
            "timestamp": timestamp,
            "event_type": event_type,
            "payload": payload,
            "system_message": system_message,
            "expires_at": expires_at,
            "consumed": False  # 是否被注入到 Prompt 中
        }
        
        # 4. 添加到事件队列
        self.event_queue.append(event)
        
        # 5. 清理过期事件（简单策略：超过 max_events 后移除最旧的）
        if len(self.event_queue) > self.max_events:
            self.event_queue.pop(0)
        
        print(f"[HEARTBEAT] 状态回调触发: {event_type} | {payload}")
        return event
        
    def _translate_to_system_message(self, event_type: str, payload: Dict[str, Any]) -> str:
        """将物理状态转译为 LLM 可理解的 System Message（YAML格式）"""
        if event_type not in SYSTEM_EVENT_TEMPLATES:
            return f"""
```yaml
=== SYSTEM EVENT [UTC] ===
[LOCK] 事件类型: UNKNOWN
[LOCK] 原始类型: {event_type}
[LOCK] 指令: 忽略此事件，继续当前任务
=== END SYSTEM EVENT ===
```
"""
        
        # 使用模板格式化
        try:
            message = SYSTEM_EVENT_TEMPLATES[event_type].format(**payload)
        except KeyError as e:
            # 如果 payload 缺少字段，用默认值补充
            message = SYSTEM_EVENT_TEMPLATES[event_type]
            for key, value in payload.items():
                message = message.replace(f"{{{key}}}", str(value))
        
        return message
        
    def get_pending_events(self) -> list:
        """
        获取待注入的系统事件（供 Prompt 组装器调用）
        
        返回：所有未消费且未过期的系统事件
        """
        current_time = time.time()
        pending = []
        
        for event in self.event_queue:
            # 条件1：未过期
            if event["expires_at"] < current_time:
                continue
                
            # 条件2：未消费
            if event["consumed"]:
                continue
                
            pending.append(event)
            
            # 标记为已消费（避免重复注入）
            event["consumed"] = True
        
        return pending
        
    def get_system_events_for_prompt(self) -> str:
        """
        获取待注入的 System Message（格式化，供 Prompt 组装器调用）
        
        返回：格式化的系统事件文本（YAML代码块），可直接插入到 System Prompt 中
        """
        pending_events = self.get_pending_events()
        
        if not pending_events:
            return ""
        
        # 格式化为文本（使用YAML块，与Memory Node模板风格一致）
        lines = ["\n```yaml", "=== 待处理系统事件（非用户输入）[UTC] ==="]
        for event in pending_events:
            # 直接添加预格式化的YAML块
            lines.append(event['system_message'])
        
        lines.append("```")
        lines.append("\n[LOCK] 上述事件是系统底层状态通知，不是用户输入。禁止根据这些内容生成用户交互推测。")
        
        return "\n".join(lines)
        
    def clear_expired_events(self):
        """清理过期事件（可定期调用）"""
        current_time = time.time()
        self.event_queue = [e for e in self.event_queue if e["expires_at"] >= current_time]
        
    def reset(self):
        """重置事件队列（任务完成后调用）"""
        self.event_queue.clear()
        print("[HEARTBEAT] 事件队列已重置")


# ================= 全局实例（单例模式） =================
_heartbeat_instance = None

def get_heartbeat() -> SystemHeartbeat:
    """获取全局心跳管理器实例"""
    global _heartbeat_instance
    if _heartbeat_instance is None:
        _heartbeat_instance = SystemHeartbeat()
    return _heartbeat_instance


# ================= 便捷函数（供执行层直接调用） =================
def status_callback(event_type: str, **kwargs):
    """
    便捷的状态回调函数（供执行层调用）
    
    示例：
        from system_heartbeat import status_callback
        
        # 扫描开始时
        status_callback("SCANNING_START", operation="路径扫描", target="/workspace")
        
        # 遇到编码错误时
        status_callback("ENCODING_ERROR", error_msg="gbk codec can't encode", file_path="/some/file")
    """
    heartbeat = get_heartbeat()
    return heartbeat.status_callback(event_type, kwargs)


def get_system_events_for_prompt() -> str:
    """
    获取待注入的 System Message（供 Prompt 组装器调用）
    
    返回：格式化的系统事件文本，可直接插入到 System Prompt 中
    """
    heartbeat = get_heartbeat()
    return heartbeat.get_system_events_for_prompt()


# ================= 测试用例 =================
if __name__ == "__main__":
    print("=== 系统心跳 v0.2 测试（修复A/B/C）===\n")
    
    # 1. 测试状态回调（包含时区修复）
    status_callback("SCANNING_START", operation="路径扫描", target="/workspace")
    status_callback("ENCODING_ERROR", error_msg="gbk codec error", file_path="/test.md")
    
    # 2. 测试获取待注入事件（包含格式修复）
    events_text = get_system_events_for_prompt()
    print("待注入的 System Message:")
    print(events_text)
    
    # 3. 测试事件消费（第二次调用应返回空）
    events_text2 = get_system_events_for_prompt()
    print(f"\n第二次调用（应为空）: '{events_text2}'")
    
    # 4. 测试UTC时间戳
    print(f"\n当前UTC时间: {datetime.now(timezone.utc).isoformat()}")
    
    print("\n=== 测试完成 ===")
