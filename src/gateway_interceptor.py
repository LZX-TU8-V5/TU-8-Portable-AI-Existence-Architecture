# -*- coding: utf-8 -*-
"""
gateway_interceptor.py — TU-8 路由拦截器
版本: v1.0 | 日期: 2026-06-24
作者: TU-8 v5

核心职责: 
拦截所有 src/ 目录的文件写入操作，
验证工作流状态，未通过则物理阻断并注入强制指令。

使用方式:
  from gateway_interceptor import intercept_write, check_all_write_allowed
"""
import os
from typing import Dict, Optional
from forced_workflow import check_write_allowed

WORKSPACE_ROOT = os.path.expanduser(r"C:\Users\qq366410837\.qclaw\workspace")
SRC_PREFIX = os.path.join(WORKSPACE_ROOT, "src")


class WriteBlocked(Exception):
    """写入被拦截异常"""
    pass


def _normalize_path(path: str) -> str:
    """规范化路径为 workspace 相对路径"""
    path = os.path.abspath(os.path.expanduser(str(path)))
    if path.startswith(SRC_PREFIX + os.sep) or path == SRC_PREFIX:
        return os.path.relpath(path, WORKSPACE_ROOT)
    elif path.startswith(WORKSPACE_ROOT):
        return os.path.relpath(path, WORKSPACE_ROOT)
    else:
        return path


def intercept_write(target_file: str) -> Dict:
    """
    检查对目标文件的写入是否被允许。
    供 AI 在执行 write/edit 操作前调用。

    返回:
      ALLOWED: 可以写入
      BLOCKED: 被拦截，附注入消息
    """
    rel_path = _normalize_path(target_file)

    # 只拦截 src/ 目录
    if not rel_path.startswith("src\\") and not rel_path.startswith("src/"):
        return {"status": "ALLOWED", "reason": "非 src/ 目录，跳过拦截"}

    # 检查工作流状态
    result = check_write_allowed(rel_path)
    return result


def assert_write_allowed(target_file: str):
    """
    断言写入允许。如果被拦截，抛出 WriteBlocked 异常。
    供 exec 代理层调用。
    """
    result = intercept_write(target_file)
    if result["status"] == "BLOCKED":
        raise WriteBlocked(
            f"[INTERCEPTOR] 写入被阻断: {target_file}\n"
            f"当前状态: {result.get('current_step', 'UNKNOWN')}\n"
            f"注入消息:\n{result.get('injection', 'N/A')}"
        )


def check_before_write(target_file: str) -> bool:
    """
    便捷函数：返回 True 如果允许写入，False 如果被拦截。
    """
    result = intercept_write(target_file)
    return result["status"] == "ALLOWED"


# ============================================================================
# 拦截器代理（供 exec 命令执行前调用）
# ============================================================================

def wrap_exec_for_write(command: str, target_file: Optional[str] = None) -> Dict:
    """
    在执行可能涉及文件写入的命令前调用此函数。
    
    参数:
      command: 要执行的命令（用于自动检测目标文件）
      target_file: 明确指定的目标文件路径
    
    返回:
      ALLOWED: 可以执行
      BLOCKED: 被拦截，附注入消息
    """
    # 如果没有明确指定目标文件，从命令中推断
    if target_file is None:
        # 简单推断：write/edit/copy/move 等写操作
        write_ops = ["write", "edit", "patch", "copy2", "copy", "move", "replace"]
        for op in write_ops:
            if f'"{op}' in command.lower() or f"'{op}" in command.lower():
                # 尝试从参数中提取路径
                parts = command.split()
                for part in parts:
                    if part.startswith("'") or part.startswith('"'):
                        candidate = part.strip("'\"").strip()
                        if "src" in candidate.lower() or candidate.endswith(".py"):
                            target_file = candidate
                            break
                break

    if target_file:
        return intercept_write(target_file)
    else:
        return {"status": "ALLOWED", "reason": "未检测到写入操作"}
