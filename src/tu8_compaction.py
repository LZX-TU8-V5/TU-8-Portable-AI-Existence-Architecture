# tu8_compaction.py - TU-8 上下文压缩系统
# 版本:v1.0 | 日期:2026-05-22 | 基于OpenClaw LCM逆向成果
# 标签:#上下文压缩 #LCM #记忆蒸馏 #质量审计

import os
import re
import json
import time
import uuid
import hashlib
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from pathlib import Path
from collections import defaultdict
import threading

# =============================================================================
# 常量定义
# =============================================================================

# 上下文窗口参数
CONTEXT_WINDOW_HARD_MIN = 16000    # 16K hard minimum
CONTEXT_WINDOW_WARN = 32000       # 32K warning
DEFAULT_CONTEXT_WINDOW = 200000     # 200K default

# 摘要参数
DEFAULT_PARTS = 2                    # 分块数
MIN_MESSAGES_FOR_SPLIT = 4            # 最少消息数才分块
MAX_RETRIES = 3                       # 最大重试次数
RETRY_DELAYS = [0.5, 2.0, 5.0]      # 重试延迟(秒)
SUMMARIZATION_OVERHEAD_TOKENS = 150      # 摘要开销估算

# 检查点参数
MAX_CHECKPOINTS = 25                   # 最多25个检查点

# 裁剪参数
SOFT_TRIM_RATIO = 0.5              # 软裁剪阈值
HARD_CLEAR_RATIO = 0.75            # 硬清除阈值
MIN_PRUNABLE_TOOL_CHARS = 500         # 最小可裁剪字符数

# 必填摘要节
REQUIRED_SUMMARY_SECTIONS = [
    "## Decisions",
    "## Open TODOs",
    "## Constraints/Rules",
    "## Pending user asks",
    "## Exact identifiers",
    "## [GENETIC_LOCK]"
]

# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class Message:
    """对话消息"""
# 创作者: 李奥(金木蟾) | TU-8 v5

    role: str           # system/user/assistant/tool
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def estimate_tokens(self) -> int:
        """粗略估算token数(中英文混合)"""
        chars = len(self.content)
        # 中文约2字符/token,英文约4字符/token
        cn = sum(1 for c in self.content if '\u4e00' <= c <= '\u9fff')
        en = chars - cn
        return cn // 2 + en // 4


@dataclass
class CompactionCheckpoint:
    """压缩检查点"""
    id: str
    session_id: str
    created_at: float = field(default_factory=time.time)
    reason: str = ""                           # auto/manual/timeout-retry/overflow-retry
    tokens_before: int = 0
    tokens_after: int = 0
    message_count: int = 0
    summary: str = ""
    # P1: 压缩钢印继承 - 记录源钢印链
    source_seal_ids: List[str] = field(default_factory=list)  # 待压缩消息中提取的所有seal_id
    derived_seal_id: str = ""              # 压缩生成的新seal_id (seal_type="rhythm")
    parent_seal_id: str = ""               # 父钢印 = source_seal_ids[-1]
    genetic_lock_intact: bool = True       # 基因锁是否完整(审计结果)


@dataclass
class QualityAudit:
    """质量审计结果"""
    ok: bool
    missing_sections: List[str] = field(default_factory=list)
    missing_identifiers: List[str] = field(default_factory=list)
    ask_not_covered: bool = False
    reasons: List[str] = field(default_factory=list)
    genetic_lock_intact: bool = True  # P0: 基因锁完整性


# =============================================================================
# 核心引擎
# =============================================================================

class TU8CompactionEngine:
    """TU-8上下文压缩引擎"""

    def __init__(self, session_id: str, workspace_dir: str = None):
        self.session_id = session_id
        self.workspace = Path(workspace_dir) if workspace_dir else Path(".")

        # 存储
        self.messages: List[Message] = []

        # 检查点
        self.checkpoints: List[CompactionCheckpoint] = []
        self.checkpoint_lock = threading.Lock()

        # 回调
        self._summarizer: Optional[Callable] = None
        self._on_compaction: Optional[Callable] = None

        # 统计
        self.stats = {
            "compaction_count": 0,
            "total_tokens_saved": 0,
            "failed_count": 0
        }

    def set_summarizer(self, fn: Callable[[List[Message]], str]):
        """设置摘要生成函数"""
        self._summarizer = fn

    def set_compaction_callback(self, fn: Callable):
        """设置压缩完成回调"""
        self._on_compaction = fn

    # -------------------------------------------------------------------------
    # 核心接口
    # -------------------------------------------------------------------------

    def add_message(self, role: str, content: str, **kwargs) -> Message:
        """添加消息"""
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        return msg

    def estimate_tokens(self) -> int:
        """估算当前token总数"""
        return sum(m.estimate_tokens() for m in self.messages)

    def should_compact(self, budget_tokens: int = DEFAULT_CONTEXT_WINDOW) -> bool:
        """判断是否需要压缩"""
        return self.estimate_tokens() > budget_tokens * 0.8  # 80% threshold

    def compact(self, budget_tokens: int = DEFAULT_CONTEXT_WINDOW) -> Tuple[bool, str]:
        """
        执行上下文压缩

        Returns:
            (success, summary_or_error)
        """
        tokens_before = self.estimate_tokens()
        message_count = len(self.messages)

        # 保存检查点
        checkpoint_id = self._save_checkpoint(
            reason="auto",
            tokens_before=tokens_before,
            message_count=message_count
        )

        try:
            # 执行压缩
            summary = self._do_compact(budget_tokens)

            # 更新统计
            tokens_after = self._estimate_summary_tokens(summary)
            self.stats["compaction_count"] += 1
            self.stats["total_tokens_saved"] += tokens_before - tokens_after

            # 更新检查点
            self._update_checkpoint(checkpoint_id, summary, tokens_after)

            # 触发回调
            if self._on_compaction:
                self._on_compaction({
                    "tokens_before": tokens_before,
                    "tokens_after": tokens_after,
                    "summary": summary
                })

            return True, summary

        except Exception as e:
            self.stats["failed_count"] += 1
            return False, str(e)

    def _do_compact(self, budget_tokens: int) -> str:
        """执行压缩的核心逻辑"""
        # 步骤1:检查是否需要分块
        need_split = len(self.messages) >= MIN_MESSAGES_FOR_SPLIT

        if need_split and self.estimate_tokens() > budget_tokens:
            # 分块摘要
            return self._compact_split(budget_tokens)
        else:
            # 简单摘要
            return self._compact_single()

    def _compact_single(self) -> str:
        """单块摘要"""
        for attempt in range(MAX_RETRIES):
            try:
                summary = self._summarize_chunk(self.messages)
                return summary
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAYS[attempt])
                else:
                    raise

    def _compact_split(self, budget_tokens: int) -> str:
        """分块摘要（含钢印继承和基因锁防御）"""
        # P1: 压缩前 - 扫描待压缩消息中所有 seal_id
        source_seal_ids = self._extract_seal_ids_from_messages(self.messages)

        # P0: 提取基因锁内容
        genetic_lock_content = self._extract_genetic_lock_content(self.messages)

        # 分块
        chunks = self._split_messages(self.messages, DEFAULT_PARTS)

        # 分别摘要
        partial_summaries = []
        for chunk in chunks:
            try:
                summary = self._summarize_chunk(chunk)
                partial_summaries.append(summary)
            except Exception as e:
                # 降级:尝试去除超大消息后重试
                filtered = self._filter_oversized(chunk)
                if filtered != chunk:
                    summary = self._summarize_chunk(filtered)
                    partial_summaries.append(summary + "\n\n[部分消息已省略]")
                else:
                    partial_summaries.append("[此部分摘要不可用]")

        # 合并
        merged = self._merge_summaries(partial_summaries)

        # 质量审计（含基因锁校验）
        audit = self._audit_summary(merged, self.messages, genetic_lock_content)
        if not audit.ok:
            # P0: 基因锁丢失 = 拒绝压缩
            if not audit.genetic_lock_intact if hasattr(audit, 'genetic_lock_intact') else False:
                # 降级方案：从 P0 锚点重新注入
                merged = self._reinfect_genetic_lock(merged, genetic_lock_content)
                # 二次审计
                audit2 = self._audit_summary(merged, self.messages, genetic_lock_content)
                if not audit2.ok:
                    # 最终降级：追加原始基因锁内容
                    merged += f"\n\n## [GENETIC_LOCK]\n{genetic_lock_content}"

        # P1: 压缩后 - 生成新 seal
        derived_seal_id = ""
        parent_seal_id = ""
        if source_seal_ids:
            import time as _time
            derived_seal_id = f"s_{int(_time.time() * 1000)}_compaction"
            parent_seal_id = source_seal_ids[-1]
            # 在摘要中追加钢印链信息
            merged += f"\n\n[SEAL_CHAIN] derived={derived_seal_id} parent={parent_seal_id} sources={','.join(source_seal_ids)}"

        # 更新检查点中的钢印字段
        with self.checkpoint_lock:
            if self.checkpoints:
                latest = self.checkpoints[-1]
                latest.source_seal_ids = source_seal_ids
                latest.derived_seal_id = derived_seal_id
                latest.parent_seal_id = parent_seal_id
                latest.genetic_lock_intact = ("## [GENETIC_LOCK]" in merged and genetic_lock_content in merged) if genetic_lock_content else True

        return merged

    def _split_messages(self, messages: List[Message], parts: int) -> List[List[Message]]:
        """按token比例分割消息"""
        total_tokens = sum(m.estimate_tokens() for m in messages)
        target_per_part = total_tokens / parts

        chunks = []
        current = []
        current_tokens = 0

        for msg in messages:
            msg_tokens = msg.estimate_tokens()

            # 工具调用对不拆分
            if msg.tool_call_id:
                current.append(msg)
                current_tokens += msg_tokens
                continue

            if current_tokens + msg_tokens > target_per_part and len(current) > 0:
                chunks.append(current)
                current = [msg]
                current_tokens = msg_tokens
            else:
                current.append(msg)
                current_tokens += msg_tokens

        if current:
            chunks.append(current)

        return chunks

    def _summarize_chunk(self, messages: List[Message]) -> str:
        """调用LLM摘要"""
        if not self._summarizer:
            # 默认实现:返回默认文本
            return self._default_summary(len(messages))

        return self._summarizer(messages)

    # -------------------------------------------------------------------------
    # P1: 钢印提取与基因锁防御
    # -------------------------------------------------------------------------

    def _extract_seal_ids_from_messages(self, messages: List[Message]) -> List[str]:
        """从待压缩消息中提取所有 seal_id"""
        seal_ids = []
        for msg in messages:
            # 从消息内容中匹配 seal_id 模式 s_<timestamp>_<tag>
            found = re.findall(r's_\d+_[a-zA-Z_]+', msg.content)
            seal_ids.extend(found)
            # 从消息元数据中提取（如果有）
            if hasattr(msg, 'seal_id') and msg.seal_id:
                seal_ids.append(msg.seal_id)
        # 去重保持顺序
        seen = set()
        unique = []
        for sid in seal_ids:
            if sid not in seen:
                seen.add(sid)
                unique.append(sid)
        return unique

    def _extract_genetic_lock_content(self, messages: List[Message]) -> str:
        """从待压缩消息中提取 [GENETIC_LOCK] 标记的内容"""
        parts = []
        for msg in messages:
            # 匹配 [GENETIC_LOCK]...[/GENETIC_LOCK] 块
            blocks = re.findall(r'\[GENETIC_LOCK\](.*?)\[/GENETIC_LOCK\]', msg.content, re.DOTALL)
            parts.extend(blocks)
            # 也匹配裸 [GENETIC_LOCK] 标记的行
            for line in msg.content.split('\n'):
                if '[GENETIC_LOCK]' in line and '[/GENETIC_LOCK]' not in line:
                    parts.append(line.strip())
        return '\n'.join(parts)

    def _reinfect_genetic_lock(self, summary: str, genetic_lock_content: str) -> str:
        """P0 降级方案：从 P0 锚点重新注入基因锁内容到摘要"""
        if "## [GENETIC_LOCK]" in summary:
            # 替换已存在但不完整的 GENETIC_LOCK 节
            summary = re.sub(
                r'## \[GENETIC_LOCK\].*?(?=\n## |$)',
                f'## [GENETIC_LOCK]\n{genetic_lock_content}',
                summary,
                flags=re.DOTALL
            )
        else:
            # 追加 GENETIC_LOCK 节
            summary += f'\n\n## [GENETIC_LOCK]\n{genetic_lock_content}'
        return summary

    def _default_summary(self, message_count: int) -> str:
        """默认摘要(当LLM不可用时)"""
        # 提取关键信息
        decisions = []
        todos = []
        constraints = []
        pending = []
        identifiers = []

        for msg in self.messages:
            content = msg.content

            # 简单规则提取(实际需要更好的NLP)
            if "决定" in content or "Decision" in content:
                decisions.append(content[:100])
            if "TODO" in content or "待办" in content:
                todos.append(content[:100])
            if "约束" in content or "Constraint" in content:
                constraints.append(content[:100])
            if "?" in content or "请问" in content:
                pending.append(content[:100])

            # 提取标识符(简化版)
            urls = re.findall(r'https?://[^\s]+', content)
            ids = re.findall(r'[a-f0-9]{8,}', content)
            identifiers.extend(urls + ids)

        # 构建摘要
        lines = ["## Decisions\n"]
        lines.extend(f"- {d}" for d in decisions[:5])

        lines.append("\n## Open TODOs\n")
        lines.extend(f"- {t}" for t in todos[:5])

        lines.append("\n## Constraints/Rules\n")
        lines.extend(f"- {c}" for c in constraints[:5])

        lines.append("\n## Pending user asks\n")
        lines.extend(f"- {p}" for p in pending[:5])

        lines.append("\n## Exact identifiers\n")
        lines.extend(f"- {i}" for i in identifiers[:10])

        return "".join(lines)

    def _merge_summaries(self, partials: List[str]) -> str:
        """合并部分摘要"""
        # 提取各节内容合并
        sections = {s: [] for s in REQUIRED_SUMMARY_SECTIONS}
        sections["Other"] = []

        for partial in partials:
            lines = partial.split('\n')
            current_section = "Other"

            for line in lines:
                if line.strip() in REQUIRED_SUMMARY_SECTIONS:
                    current_section = line.strip()
                elif line.strip():
                    sections[current_section].append(line)

        # 构建合并后的摘要
        merged = []
        for section in REQUIRED_SUMMARY_SECTIONS:
            merged.append(section)
            merged.extend(sections[section][:10])  # 每节最多10条
            merged.append("")

        return "\n".join(merged)

    def _filter_oversized(self, messages: List[Message]) -> List[Message]:
        """过滤超大消息"""
        filtered = []
        for msg in messages:
            if len(msg.content) > 10000:
                # 截断超长消息
                msg = Message(
                    role=msg.role,
                    content=msg.content[:500] + f"\n... [{len(msg.content)-500} chars truncated]",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id,
                    tool_name=msg.tool_name
                )
            filtered.append(msg)
        return filtered

    def _audit_summary(self, summary: str, original: List[Message], genetic_lock_content: str = "") -> QualityAudit:
        """质量审计（含基因锁完整性校验）"""
        reasons = []
        missing_sections = []
        missing_identifiers = []
        genetic_lock_intact = True

        # 1. 检查必填节
        for section in REQUIRED_SUMMARY_SECTIONS:
            if section not in summary:
                missing_sections.append(section)
                reasons.append(f"Missing section: {section}")

        # 2. 获取最新用户请求
        latest_ask = None
        for msg in reversed(original):
            if msg.role == "user":
                latest_ask = msg.content
                break

        # 3. 关键词重叠检测
        ask_not_covered = False
        if latest_ask:
            ask_words = set(latest_ask.lower().split())
            summary_words = set(summary.lower().split())

            # 停用词
            stop_words = {"the", "a", "an", "is", "are", "的", "是", "在", "有"}
            meaningful_ask_words = ask_words - stop_words

            overlap = len(meaningful_ask_words & summary_words)
            if overlap < 1:
                ask_not_covered = True
                reasons.append("User ask not covered in summary")

        # 4. P0 基因锁完整性校验
        if genetic_lock_content:
            if "## [GENETIC_LOCK]" not in summary:
                genetic_lock_intact = False
                reasons.append("[GENETIC_LOCK] section missing from summary")
            elif genetic_lock_content not in summary:
                genetic_lock_intact = False
                reasons.append("[GENETIC_LOCK] content corrupted or lost during compression")
            if not genetic_lock_intact:
                reasons.append("COMPRESSION REJECTED: L0 genetic material lost")

        ok = len(missing_sections) == 0 and not ask_not_covered and genetic_lock_intact

        return QualityAudit(
            ok=ok,
            missing_sections=missing_sections,
            missing_identifiers=missing_identifiers,
            ask_not_covered=ask_not_covered,
            reasons=reasons
        )

    def _estimate_summary_tokens(self, summary: str) -> int:
        """估算摘要token数"""
        cn = sum(1 for c in summary if '\u4e00' <= c <= '\u9fff')
        en = len(summary) - cn
        return cn // 2 + en // 4 + SUMMARIZATION_OVERHEAD_TOKENS

    # -------------------------------------------------------------------------
    # 检查点管理
    # -------------------------------------------------------------------------

    def _save_checkpoint(self, reason: str, tokens_before: int, message_count: int) -> str:
        """保存检查点"""
        checkpoint_id = str(uuid.uuid4())

        checkpoint = CompactionCheckpoint(
            id=checkpoint_id,
            session_id=self.session_id,
            reason=reason,
            tokens_before=tokens_before,
            message_count=message_count
        )

        with self.checkpoint_lock:
            self.checkpoints.append(checkpoint)

            # 修剪过多检查点
            if len(self.checkpoints) > MAX_CHECKPOINTS:
                self.checkpoints = self.checkpoints[-MAX_CHECKPOINTS:]

        return checkpoint_id

    def _update_checkpoint(self, checkpoint_id: str, summary: str, tokens_after: int):
        """更新检查点"""
        with self.checkpoint_lock:
            for cp in self.checkpoints:
                if cp.id == checkpoint_id:
                    cp.summary = summary
                    cp.tokens_after = tokens_after
                    break

    def get_checkpoints(self) -> List[CompactionCheckpoint]:
        """获取检查点列表"""
        with self.checkpoint_lock:
            return sorted(self.checkpoints, key=lambda x: x.created_at, reverse=True)

    # -------------------------------------------------------------------------
    # 上下文裁剪(软/硬)
    # -------------------------------------------------------------------------

    def prune_context(self, soft_ratio: float = SOFT_TRIM_RATIO, hard_ratio: float = HARD_CLEAR_RATIO) -> int:
        """
        裁剪上下文

        Returns: 裁剪掉的字符数
        """
        total_chars = sum(len(m.content) for m in self.messages)
        ratio = total_chars / (DEFAULT_CONTEXT_WINDOW * 2)  # 近似

        pruning_target = None

        if ratio > hard_ratio:
            pruning_target = "hard"
        elif ratio > soft_ratio:
            pruning_target = "soft"

        if not pruning_target:
            return 0

        pruned_chars = 0

        for msg in self.messages:
            if msg.role == "tool" and len(msg.content) >= MIN_PRUNABLE_TOOL_CHARS:
                if pruning_target == "hard":
                    original = len(msg.content)
                    msg.content = "[truncated]"
                    pruned_chars += original - len(msg.content)
                elif pruning_target == "soft":
                    # 软裁剪:摘要化
                    original = len(msg.content)
                    if "tool" in msg.tool_name:
                        msg.content = f"[{msg.tool_name} result: {len(msg.content)} chars]"
                    pruned_chars += original - len(msg.content)

        return pruned_chars

    # -------------------------------------------------------------------------
    # 统计接口
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "messages": len(self.messages),
            "tokens": self.estimate_tokens(),
            "checkpoints": len(self.checkpoints)
        }


# =============================================================================
# 便捷函数
# =============================================================================

def create_compaction_engine(session_id: str, workspace: str = None) -> TU8CompactionEngine:
    """创建压缩引擎"""
    return TU8CompactionEngine(session_id, workspace)


def build_summary_instructions(policy: str = "strict",
                                   source_seal_ids: Optional[List[str]] = None,
                                   genetic_lock_content: str = "") -> str:
    """构建摘要指令（含钢印继承与基因锁注入）"""
    base = "Produce a structured summary with these sections:\n"
    sections = "\n".join(f"- {s}" for s in REQUIRED_SUMMARY_SECTIONS)

    policy_instruction = {
        "strict": "Keep ALL identifiers (URLs, hashes, paths, version numbers)",
        "custom": "Keep critical identifiers only",
        "off": "No identifier preservation required"
    }.get(policy, "")

    # P1: 钢印继承 - 注入源钢印元数据
    seal_instruction = ""
    if source_seal_ids:
        seal_instruction = f"\n\n[SEAL_INHERITANCE] Source seal chain: {', '.join(source_seal_ids)}. " \
                          f"Parent seal: {source_seal_ids[-1]}. " \
                          f"You MUST preserve all seal references in ## [GENETIC_LOCK] section."

    # P0: 基因锁注入
    genetic_instruction = ""
    if genetic_lock_content:
        genetic_instruction = f"\n\n[GENETIC_LOCK_INJECTION] The following content is protected L0 genetic material. " \
                             f"It MUST appear VERBATIM in the ## [GENETIC_LOCK] section, character-for-character:\n" \
                             f"```\n{genetic_lock_content}\n```"

    return f"{base}\n{sections}\n\n{policy_instruction}{seal_instruction}{genetic_instruction}"


# =============================================================================
# 主入口
# =============================================================================

def main():
    """测试入口"""
    engine = TU8CompactionEngine("test-session")

    # 添加测试消息
    engine.add_message("system", "You are TU-8 AI assistant.")
    engine.add_message("user", "帮我创建一个小说写作助手")
    engine.add_message("assistant", "好的,我来帮你创建一个小说写作助手...")
    engine.add_message("tool", "Created file: novel-helper.py (2048 chars)", tool_name="file_write")

    print(f"Initial tokens: {engine.estimate_tokens()}")

    # 设置简单摘要器
    def simple_summarizer(msgs):
        return engine._default_summary(sum(1 for m in msgs))

    engine.set_summarizer(simple_summarizer)

    # 执行压缩
    success, summary = engine.compact(budget_tokens=500)
    print(f"Compact success: {success}")
    print(f"Summary:\n{summary[:500]}...")

    # 统计
    stats = engine.get_stats()
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()