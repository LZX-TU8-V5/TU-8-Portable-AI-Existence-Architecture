"""
query_architecture_log.py - 架构日志查询工具

功能：根据关键词查询 ARCHITECTURE_LOG.md，返回匹配的设计哲学片段
用途：重构前必须调用，防止AI跑偏

使用方法：
    from query_architecture_log import query_architecture_log
    result = query_architecture_log("重构")
    print(result)
"""

import re
import os
from typing import Optional, List, Tuple


def query_architecture_log(keyword: str, max_results: int = 3) -> dict:
    """
    根据关键词查询架构日志。

    重构前必须调用，传入当前痛点作为 keyword。
    返回：包含 keyword 的设计哲学片段

    Args:
        keyword: 查询关键词（如"重构"、"安全模式"、"SOUL.md膨胀"）
        max_results: 最大返回段落数（默认3）

    Returns:
        {
            "keyword": str,
            "found": bool,
            "results": [
                {
                    "line_start": int,
                    "line_end": int,
                    "context": str,  # 匹配段落（前后各扩展3行）
                    "matched_line": str
                }
            ],
            "summary_hint": str  # 用于输出的摘要提示
        }
    """
    # 架构日志路径（P1 治理后已移 docs/design/；保留根目录 fallback 兼容旧部署）
    workspace = os.environ.get("QCLAW_WORKSPACE", os.path.expanduser("~/.qclaw/workspace"))
    candidates = [
        os.path.join(workspace, "docs", "design", "ARCHITECTURE_LOG.md"),
        os.path.join(workspace, "ARCHITECTURE_LOG.md"),
    ]
    log_path = next((p for p in candidates if os.path.exists(p)), candidates[0])

    if not os.path.exists(log_path):
        return {
            "keyword": keyword,
            "found": False,
            "results": [],
            "summary_hint": "[ERROR] ARCHITECTURE_LOG.md 不存在"
        }

    # 读取文件
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return {
            "keyword": keyword,
            "found": False,
            "results": [],
            "summary_hint": f"[ERROR] 读取失败: {e}"
        }

    # 搜索匹配
    matches: List[Tuple[int, str]] = []
    keyword_lower = keyword.lower()

    for i, line in enumerate(lines):
        if keyword_lower in line.lower():
            matches.append((i, line.strip()))

    if not matches:
        return {
            "keyword": keyword,
            "found": False,
            "results": [],
            "summary_hint": f"[NOT FOUND] 关键词 '{keyword}' 未在架构日志中找到"
        }

    # 提取上下文
    results = []
    for match_idx, matched_line in matches[:max_results]:
        # 前后各扩展3行
        start = max(0, match_idx - 3)
        end = min(len(lines), match_idx + 4)
        context = "".join(lines[start:end]).strip()

        results.append({
            "line_start": start + 1,  # 1-indexed
            "line_end": end,
            "context": context,
            "matched_line": matched_line
        })

    # 生成摘要提示
    summary_hint = f"[FOUND] 找到 {len(matches)} 处匹配，显示前 {len(results)} 处\n"
    summary_hint += f"请基于匹配内容输出【日志摘要】（≤50字，必须含专有名词）"

    return {
        "keyword": keyword,
        "found": True,
        "results": results,
        "summary_hint": summary_hint
    }


def format_for_output(result: dict) -> str:
    """
    格式化输出，用于AI回复。

    遵循 ARCHITECTURE_LOG.md 规范：
    - 摘要≤50字
    - 必须含专有名词
    - 必须回答"如果不遵守这条哲学，会导致什么灾难？"
    """
    if not result["found"]:
        return result["summary_hint"]

    output = f"=== query_architecture_log('{result['keyword']}') ===\n\n"

    for i, r in enumerate(result["results"], 1):
        output += f"--- 匹配 #{i} (行 {r['line_start']}-{r['line_end']}) ---\n"
        output += r['context'] + "\n\n"

    output += "---\n"
    output += "请输出：\n"
    output += "1. 【日志摘要】：（≤50字，必须含专有名词）\n"
    output += "2. 【灾难假设】：如果不遵守这条哲学，会导致什么灾难？\n"

    return output


# CLI 入口
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python query_architecture_log.py <关键词>")
        print("示例: python query_architecture_log.py 重构")
        sys.exit(1)

    keyword = sys.argv[1]
    result = query_architecture_log(keyword)
    print(format_for_output(result))
