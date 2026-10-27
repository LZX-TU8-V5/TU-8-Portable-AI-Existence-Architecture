# -*- coding: utf-8 -*-
"""测试 Planner→Toolchain 端到端集成"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
sys.path.insert(0, r'D:\qq366410837\.qclaw\workspace\src')
sys.path.insert(0, r'D:\tu8-v5\TU-8')

from tu8_toolchain import PlannerToolchainBridge
from tu8_planner import TU8Planner, Plan, Task, PlanStatus

def main():
    print("=" * 60)
    print("TU-8 Planner→Toolchain 端到端测试")
    print("=" * 60)

    # 1. 创建 Planner 和 Bridge
    planner = TU8Planner(workspace=r'D:\qq366410837\.qclaw\workspace')
    bridge = PlannerToolchainBridge(workspace=r'D:\qq366410837\.qclaw\workspace')

    # 2. 创建简单计划
    plan = Plan(id='test_plan_001', goal='测试 TU-8 Toolchain 集成')
    
    # Task 1: 文件读取
    t1 = Task(
        id='task_1',
        description='读取 SOUL.md 文件前10行',
        tags=['file_read'],
    )
    t1.params = {'path': r'C:\Users\qq366410837\.openclaw\workspace\SOUL.md', 'limit': 10}
    plan.add_task(t1)
    
    # Task 2: Shell 执行
    t2 = Task(
        id='task_2',
        description='执行 python --version',
        tags=['shell', 'exec'],
    )
    t2.params = {'command': 'python --version'}
    plan.add_task(t2)

    # 3. 批准并执行
    print("\n[步骤1] 批准计划...")
    plan.approve()
    
    print("[步骤2] 执行计划...")
    result_plan = planner.execute_plan(plan, agent_callback=bridge)

    # 4. 查看结果
    print("\n" + "=" * 60)
    print("执行结果")
    print("=" * 60)
    for tid, task in result_plan.tasks.items():
        status_icon = "[OK]" if task.status.value == "done" else "[FAIL]"
        result_preview = task.result[:80] if task.result else "无结果"
        print(f"{status_icon} {tid}: {task.status.value}")
        print(f"   -> {result_preview}")

    # 5. 查看 pending tool calls
    print("\n" + "=" * 60)
    print("待执行工具调用")
    print("=" * 60)
    pending = bridge.get_pending_tool_calls()
    if pending:
        for tid, call in pending.items():
            tool = call.get('tool', 'unknown')
            params = call.get('params', {})
            print(f"{tid}: {tool}({params})")
    else:
        print("(无)")

    # 6. 统计
    print("\n" + "=" * 60)
    print("工具链统计")
    print("=" * 60)
    stats = bridge.get_toolchain_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\n[OK] 测试完成")
    return result_plan.status == PlanStatus.DONE


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
