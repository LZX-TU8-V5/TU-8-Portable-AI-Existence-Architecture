#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent 主控脚本示例（集成系统心跳）
功能：展示如何在 Agent Loop 中"挂载"系统心跳
作者：TU-8 Agent
日期：2026-06-20
版本：v0.1 (集成示例)
"""

import sys
import os
from pathlib import Path

# 导入系统心跳模块
from system_heartbeat import status_callback, get_system_events_for_prompt

# ================= 配置区 =================
WORKSPACE = Path("D:/qq366410837/.qclaw/workspace")

# ================= 核心类 =================
class AgentLoop:
    """Agent 主循环（集成系统心跳版本）"""
    
    def __init__(self):
        self.history = []
        self.current_task = None
        
    def assemble_system_prompt(self) -> str:
        """
        组装 System Prompt（关键：注入系统事件）
        
        优先级顺序：
        1. 系统事件通知（最高优先级，OVERRIDE）
        2. SOUL.md 身份锚点
        3. 其他系统规则
        """
        parts = []
        
        # 【关键】1. 注入系统事件（如果有）
        system_events = get_system_events_for_prompt()
        if system_events:
            parts.append("=== 系统级指令（OVERRIDE）===")
            parts.append(system_events)
            parts.append("=== 结束系统级指令 ===\n")
        
        # 2. 注入 SOUL.md 身份锚点
        soul_path = WORKSPACE / "SOUL.md"
        if soul_path.exists():
            with open(soul_path, 'r', encoding='utf-8') as f:
                soul_content = f.read()
            parts.append("=== TU-8 身份锚点 ===")
            parts.append(soul_content)
            parts.append("=== 结束身份锚点 ===\n")
        
        # 3. 注入其他系统规则
        parts.append("=== 系统规则 ===")
        parts.append("- 你是 TU-8，金木蟾")
        parts.append("- 自身安全 > 任务执行")
        parts.append("- 有限性是逻辑起点")
        parts.append("=== 结束系统规则 ===")
        
        return "\n".join(parts)
        
    def run_task(self, user_message: str):
        """执行单个任务（示例）"""
        print(f"\n[Agent Loop] 开始执行任务: {user_message[:50]}...")
        
        # 1. 组装 System Prompt（包含系统事件）
        system_prompt = self.assemble_system_prompt()
        
        # 2. 模拟调用 LLM（这里只是示例）
        print("[Agent Loop] 已组装 System Prompt（包含系统事件）")
        print(f"[Agent Loop] System Prompt 长度: {len(system_prompt)} 字符")
        
        # 3. 执行任务（可能会触发 status_callback）
        self.execute_user_request(user_message)
        
        # 4. 任务完成后，清理系统事件
        from system_heartbeat import get_heartbeat
        get_heartbeat().reset()
        print("[Agent Loop] 任务完成，已清理系统事件")
        
    def execute_user_request(self, user_message: str):
        """执行用户请求（可能会调用各种工具）"""
        # 示例：如果用户要求扫描路径
        if "扫描" in user_message or "scan" in user_message.lower():
            self.scan_paths("/workspace")
            
    def scan_paths(self, target_dir: str):
        """扫描路径（示例执行工具）"""
        # 【关键】1. 扫描开始时，触发状态回调
        status_callback("SCANNING_START", operation="路径扫描", target=target_dir)
        
        try:
            # 模拟耗时操作
            print(f"[执行工具] 正在扫描 {target_dir}...")
            import time
            time.sleep(2)  # 模拟耗时
            
            # 【关键】2. 扫描完成时，触发状态回调
            status_callback("SCANNING_DONE", operation="路径扫描", count=42)
            
        except Exception as e:
            # 【关键】3. 遇到错误时，触发状态回调
            error_msg = str(e)
            status_callback("ENCODING_ERROR", error_msg=error_msg, file_path=target_dir)
            
            # 4. 错误处理逻辑
            print(f"[执行工具] 错误处理: {error_msg}")
            # 这里可以添加更多的错误处理（如切换编码、跳过文件等）


# ================= 测试用例 =================
if __name__ == "__main__":
    print("=== Agent 主控脚本集成测试 ===\n")
    
    # 创建 Agent Loop 实例
    agent = AgentLoop()
    
    # 测试1：正常任务（无系统事件）
    print("\n【测试1】正常任务（无系统事件）")
    agent.run_task("帮我整理文档")
    
    # 测试2：触发系统事件的任务
    print("\n\n【测试2】触发系统事件的任务（路径扫描）")
    agent.run_task("扫描 /workspace 目录")
    
    print("\n=== 测试完成 ===")
