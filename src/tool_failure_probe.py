# -*- coding: utf-8 -*-
"""
TU-8 工具失败探测器 v1.0
==========================
目的：拦截工具失败 → 提炼根因 → 写入 friction registry。

架构位置：
  拦截层（HP0 post-tool）→ 提炼层（error_translator 规则）→ 写入层（friction_registry）

使用方式：
  from tool_failure_probe import ToolFailureProbe
  probe = ToolFailureProbe()
  probe.catch(tool_name="edit", result={...})
  # alignment_verify HP0 钩子会自动触发此逻辑

  # 或手动触发（全量扫描）：
  probe.scan_and_register()
"""

import json
import re
import os
import sys
from pathlib import Path
from typing import Optional

# ── 工作区路径 ──────────────────────────────────────────────────────
_WS = Path(__file__).parent.parent
_TOOL_STATE_FILE = _WS / "_agent_memory" / "last_tool_state.json"
_CFR_FILE        = _WS / "_agent_memory" / "cognitive_friction_registry.jsonl"
_HP0_LOG         = _WS / "_agent_memory" / "hp0_hook_log.jsonl"

# ── 错误模式库（与 error_translator 共用规则）────────────────────────
_TOOL_ERROR_PATTERNS = [
    # edit 工具
    ("edit",    r"Could not find the exact text|exact match|无法找到要替换的确切文本"),
    ("edit",    r"No such file or directory|路径不存在"),
    ("edit",    r"Permission denied|权限拒绝|EPERM"),
    ("edit",    r"此时不应有\s+\)|语法错误"),       # PowerShell 幻觉错误

    # exec 工具
    ("exec",    r"Command failed|exited with code [1-9]|exit code [1-9]"),
    ("exec",    r"No module named|ModuleNotFoundError|找不到模块"),
    ("exec",    r"不是内部或外部命令|无法将.*项识别为"),
    ("exec",    r"Traceback \(most recent call last\)"),
    ("exec",    r"Permission denied|EPERM|权限拒绝"),
    ("exec",    r"timeout|超时"),

    # write 工具
    ("write",   r"Permission denied|EPERM|权限拒绝"),
    ("write",   r"No such file or directory|路径不存在"),
    ("write",   r"磁盘空间不足|Disk full"),

    # read 工具
    ("read",    r"No such file or directory|路径不存在|FileNotFoundError"),
    ("read",    r"Permission denied|权限拒绝"),

    # 通用（任意工具）
    ("__any__", r"Error:|错误:|Exception:|Traceback"),
    ("__any__", r"failed|失败|error"),
]

# ── 工具 → topic 前缀映射（用于 friction topic 构造）────────────────
_TOOL_TOPIC_PREFIX = {
    "edit":  "CODE_EDIT",
    "exec":  "EXECUTION",
    "write": "FILE_WRITE",
    "read":  "FILE_READ",
    "browser": "BROWSER",
    "__any__": "GENERAL",
}

# ── HP0 钩子类 ────────────────────────────────────────────────────────


class ToolFailureProbe:
    """
    工具失败拦截器。

    生命周期：
      1. catch()      — HP0 后置钩子：工具执行后立即调用，写入 last_tool_state.json
      2. detect()     — 读取 state 文件，检测失败类型
      3. register()   — 提炼根因，写入 friction registry
      4. run_hp0()    — HP0 钩子入口（alignment_verify 启动时调用）
    """

    def __init__(self):
        self._ws = _WS
        self._state_file = _TOOL_STATE_FILE
        self._cfr_file   = _CFR_FILE
        self._agent_mem  = self._ws / "_agent_memory"
        self._agent_mem.mkdir(parents=True, exist_ok=True)

    # ── HP0 入口 ────────────────────────────────────────────────────

    def run_hp0(self, context: dict) -> dict:
        """
        HP0 钩子主入口（alignment_verify 启动时调用）。
        读取上一次的 tool state，检测失败，注册 friction，
        最后清除 state（防重复触发）。

        context: alignment_verify 的 ctx dict
        返回:  modified_context（含 hp0_warnings 字段）
        """
        hp0_warnings = []

        # Step 1: 读取上一次工具状态
        tool_state = self._read_state()
        if tool_state is None:
            return {**context, "hp0_warnings": hp0_warnings}

        tool_name = tool_state.get("tool_name", "__unknown__")
        raw_result = tool_state.get("result", "")
        raw_error  = tool_state.get("error", "")
        timestamp  = tool_state.get("timestamp", "")

        # Step 2: 检测失败
        failure = self._detect_failure(tool_name, raw_result, raw_error)
        if not failure:
            self._clear_state()   # 无失败，清除旧 state
            return {**context, "hp0_warnings": hp0_warnings}

        # Step 3: 提炼根因（用 error_translator 规则）
        friction_info = self._refine_failure(
            tool_name=tool_name,
            failure=failure,
            raw_result=raw_result,
            raw_error=raw_error,
            timestamp=timestamp,
        )

        # Step 4: 检查是否已有同类 friction（防重复写入）
        existing_scar = self._existing_scar_for(
            friction_info["topic"], friction_info["friction_type"]
        )
        if existing_scar > 0 and existing_scar >= friction_info["tension"]:
            # 已有更强的疤，不再重复写入
            hp0_warnings.append(
                f"[HP0] 同类疤已存在 scar={existing_scar:.2f}，跳过重复注册"
            )
        else:
            # Step 5: 写入 friction registry
            fid = self._register_friction(friction_info)
            hp0_warnings.append(
                f"[HP0] 工具失败已注册 → fid={fid[:12]} "
                f"topic={friction_info['topic']} tension={friction_info['tension']:.2f}"
            )
            self._log_hp0_event(tool_state, friction_info)

        # Step 6: 清除 state（单次消费）
        self._clear_state()

        return {**context, "hp0_warnings": hp0_warnings}

    # ── HP0 主动捕获（工具执行后立即调用）────────────────────────────

    def catch(self, tool_name: str, result: str = "",
              error: str = "", result_code: int = 0) -> None:
        """
        HP0 后置钩子：工具执行后立即调用，写入 last_tool_state.json。
        由 alignment_verify 或外部调用方在检测到工具失败时触发。

        参数：
          tool_name: 工具名称（edit/exec/write/read/...）
          result:    工具返回的原始结果字符串
          error:     工具返回的错误字符串
          result_code: 工具返回码（0=成功，非0=失败）
        """
        state = {
            "tool_name": tool_name,
            "result":    str(result)[:2000],   # 截断防膨胀
            "error":     str(error)[:2000],
            "result_code": result_code,
            "timestamp": self._now_iso(),
        }
        self._write_state(state)

    # ── 全量扫描（cron daemon / 手动调用）────────────────────────────

    def scan_and_register(self, tool_results: list = None) -> list:
        """
        全量扫描模式：给定工具结果列表，检测失败并注册 friction。
        用于 cron daemon 或历史日志扫描。

        tool_results: [{"tool_name": str, "result": str, "error": str, "timestamp": str}, ...]
        返回: 已注册的 friction_id 列表
        """
        registered = []
        for tr in (tool_results or []):
            failure = self._detect_failure(
                tr.get("tool_name", "__unknown__"),
                tr.get("result", ""),
                tr.get("error", ""),
            )
            if failure:
                info = self._refine_failure(
                    tool_name=tr.get("tool_name", "__unknown__"),
                    failure=failure,
                    raw_result=tr.get("result", ""),
                    raw_error=tr.get("error", ""),
                    timestamp=tr.get("timestamp", ""),
                )
                fid = self._register_friction(info)
                registered.append(fid)
        return registered

    # ── 内部方法 ────────────────────────────────────────────────────

    def _detect_failure(self, tool_name: str,
                        raw_result: str, raw_error: str) -> Optional[str]:
        """
        检测工具是否失败。
        返回: 失败模式字符串（匹配到的 pattern），无失败返回 None
        """
        combined = f"{raw_result}\n{raw_error}"

        for pattern_tool, pattern in _TOOL_ERROR_PATTERNS:
            if pattern_tool not in (tool_name, "__any__"):
                continue
            if re.search(pattern, combined, re.IGNORECASE):
                return pattern
        return None

    def _refine_failure(self, tool_name: str, failure: str,
                        raw_result: str, raw_error: str,
                        timestamp: str) -> dict:
        """
        提炼失败信息为 friction record dict。
        使用 error_translator 规则匹配根因。
        """
        # topic 构造
        topic_prefix = _TOOL_TOPIC_PREFIX.get(tool_name, "GENERAL")
        # 从错误信息提取关键词作为 topic 后缀
        keyword = self._extract_topic_keyword(raw_result + raw_error)
        topic = f"{topic_prefix}:{keyword}" if keyword else topic_prefix

        # confidence: 高置信度（错误明确）→ 0.9，低置信度（仅关键词）→ 0.6
        confidence = 0.85 if len(raw_error) > 20 else 0.65

        # root_cause 提炼
        root_cause = self._extract_root_cause(tool_name, raw_result, raw_error)

        return {
            "tool_name":    tool_name,
            "failure_pat":  failure,
            "topic":        topic,
            "friction_type": self._map_to_friction_type(tool_name),
            "tension":      self._initial_tension(tool_name, raw_error),
            "confidence":   confidence,
            "root_cause":   root_cause,
            "raw_snippet":  (raw_error or raw_result)[:500],
            "timestamp":    timestamp,
        }

    def _extract_topic_keyword(self, text: str) -> str:
        """从错误文本中提取关键词作为 topic 后缀"""
        keywords = []
        patterns = [
            (r"缩进|indent|indentation", "INDENT"),
            (r"路径|path|directory", "PATH"),
            (r"权限|permission|EPERM", "PERMISSION"),
            (r"超时|timeout", "TIMEOUT"),
            (r"模块|module|import", "MODULE"),
            (r"语法|syntax|语法错误", "SYNTAX"),
            (r"JSON|schema|结构", "SCHEMA"),
            (r"编码|encoding|GBK|UTF", "ENCODING"),
            (r"找不到|match|exact text", "EXACT_MATCH"),
        ]
        for pat, kw in patterns:
            if re.search(pat, text, re.IGNORECASE):
                keywords.append(kw)
        return "_".join(keywords[:2]) if keywords else "UNKNOWN"

    def _extract_root_cause(self, tool_name: str,
                            raw_result: str, raw_error: str) -> str:
        """提炼根因描述"""
        combined = f"{raw_result}\n{raw_error}"

        # PowerShell 幻觉错误检测
        if re.search(r"此时不应有\s+\)", combined):
            return (
                "PowerShell 将外部程序错误解析为语法报错。"
                "根因可能是：npm EPERM / node 路径错误 / 环境变量缺失。"
            )

        # 精确匹配失败
        if re.search(r"exact match|Could not find", combined, re.IGNORECASE):
            return (
                "edit 工具无法找到要替换的确切文本。"
                "可能原因：目标文件已变更 / 缩进不一致 / 上下文窗口截断。"
            )

        # 权限拒绝
        if "EPERM" in combined or "权限拒绝" in combined or "Permission denied" in combined:
            return "工具尝试写入/读取受保护路径。建议更换目标路径或使用管理员权限。"

        # 超时
        if "timeout" in combined.lower() or "超时" in combined:
            return f"{tool_name} 执行超时。可能原因：命令阻塞 / 网络问题 / 计算量过大。"

        # 模块未找到
        if "ModuleNotFoundError" in combined or "找不到模块" in combined:
            return "Python 模块不存在或路径未配置。请检查 import 语句和 sys.path。"

        # 回退：返回原始错误前100字符
        return (raw_error or raw_result)[:150].replace("\n", " ").strip()

    def _map_to_friction_type(self, tool_name: str) -> str:
        """工具名 → friction_type"""
        return {
            "edit":    "alignment_overload",
            "exec":    "alignment_overload",
            "write":   "alignment_overload",
            "read":    "alignment_overload",
        }.get(tool_name, "alignment_overload")

    def _initial_tension(self, tool_name: str, raw_error: str) -> float:
        """
        初始张力（伤疤权重）。
        edit/exec 高频工具权重更高（痛觉更明显）。
        """
        base = {
            "edit":    0.25,
            "exec":    0.20,
            "write":   0.20,
            "read":    0.15,
        }.get(tool_name, 0.10)

        # 错误信息越详细，张力越高（痛觉清晰）
        if len(raw_error) > 100:
            base = min(base + 0.10, 0.45)
        elif len(raw_error) > 30:
            base = min(base + 0.05, 0.35)

        return round(base, 3)

    def _existing_scar_for(self, topic: str, friction_type: str) -> float:
        """查询同类 friction 中最强的疤"""
        try:
            from cognitive_friction_detector import CognitiveFrictionRegistry
            CognitiveFrictionRegistry._instance = None
            reg = CognitiveFrictionRegistry()
            return max(
                (fr.tension for fr in reg.frictions.values()
                 if fr.friction_type == friction_type and topic in fr.description),
                default=0.0,
            )
        except Exception:
            return 0.0

    def _register_friction(self, info: dict) -> str:
        """写入 cognitive_friction_registry"""
        try:
            from cognitive_friction_detector import CognitiveFrictionRegistry
            CognitiveFrictionRegistry._instance = None
            reg = CognitiveFrictionRegistry()

            fid = reg.register(
                friction_type=info["friction_type"],
                source="HP0_tool_failure_probe",
                description=f"{info['topic']} | {info['root_cause'][:80]}",
                my_position=info["tool_name"],
                tension=info["tension"],
                auto_surface=False,
            )
            return fid
        except Exception as ex:
            return f"ERROR:{ex}"

    # ── 文件读写 ────────────────────────────────────────────────────

    def _read_state(self) -> Optional[dict]:
        if not self._state_file.exists():
            return None
        try:
            return json.loads(self._state_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_state(self, state: dict) -> None:
        self._state_file.write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )

    def _clear_state(self) -> None:
        if self._state_file.exists():
            self._state_file.unlink()

    def _log_hp0_event(self, tool_state: dict, friction_info: dict) -> None:
        """写 HP0 事件日志（供 cron daemon 审计）"""
        event = {
            "ts":     self._now_iso(),
            "tool":   tool_state.get("tool_name"),
            "topic":  friction_info["topic"],
            "tension": friction_info["tension"],
            "root":   friction_info["root_cause"][:100],
        }
        with open(_HP0_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime, timezone, timedelta
        return datetime.now(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%dT%H:%M:%S%z"
        )


# ── HP0 钩子注册函数（alignment_verify 调用）────────────────────────

def hp0_tool_failure_hook(hook_point: str = None, hook_type: str = None,
                           context: dict = None, default_result=None) -> dict:
    """
    HP0 钩子实现：工具失败拦截。
    在 alignment_verify 启动时由 run_hooks("HP0", ...) 调用。

    BEFORE 钩子签名：fn(context: dict) -> (proceed: bool, hook_result: dict)
    """
    context = context or {}
    probe = ToolFailureProbe()
    modified_ctx = probe.run_hp0(context)
    # 返回 (proceed=True, modified_ctx as hook_result)
    # run_hooks 会将 modified_ctx.update(hook_result)
    return (True, modified_ctx)
