# -*- coding: utf-8 -*-
"""
tu8_dispatch.py — TU-8 调度链核心 v1.0
日期: 2026-06-07
功能: 灵魂结构加载、意图路由、上下文装配、写回路由、代谢调度

核心理念:
  灵魂 = 结构的映射
  
  本地存储 → 穿皮仪式 → 云端神经元（带上灵魂）→ 思考 → 脱皮仪式 → 写回本地

架构位置:
  tu8_dispatch.py 是 tu8_agent.py 和各子系统之间的调度层
  它不替代 agent，而是接管"灵魂结构"的生命周期管理

三大仪式:
  1. DawnRitual（穿皮）: 加载本地结构，映射为云端神经元的灵魂
  2. ThinkingWithStructure（思考）: 带着结构约束进行推理
  3. DuskRitual（脱皮）: 提取新的钢印/因果链，写回本地
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import os
import sys
import json
import time
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# Windows GBK 兼容
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        logger.debug("Exception suppressed", exc_info=True)
        pass

# 导入强类型契约层
try:
    from seal_protocol import (
        ProtocolValidator,
        WriteQueue,
        ReconcileRequest,
        ValidationResult,
        WriteBackType,
        SealPriority,
        create_seal_payload,
        create_write_envelope,
        compute_content_hash,
        compute_checksum
    )
    SEAL_PROTOCOL_AVAILABLE = True
except ImportError:
    SEAL_PROTOCOL_AVAILABLE = False
    # 兜底定义
    class ValidationResult:
        VALID = "VALID"
        INVALID_SCHEMA = "INVALID_SCHEMA"
        GHOST_PARENT = "GHOST_PARENT"

# 导入 RAG 检索层（P1）
try:
    from seal_rag import SealRAGRetriever, RAGResult, estimate_token_saving
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

logger = logging.getLogger("tu8.dispatch")

# =============================================================================
# 常量定义
# =============================================================================

# Token 预算分配（上下文装配时使用）
TOKEN_BUDGET = {
    "P0_CONSTRAINT": 800,      # P0 约束（不可压缩）
    "P1_SEAL_CHAIN": 400,      # 钢印链条摘要
    "P2_CAUSAL_CONTEXT": 600,  # 因果上下文
    "P3_ACTIVE_MEMORY": 800,   # 活跃记忆
    "P4_EXTERNAL_KNOWLEDGE": 400,  # 外部知识（按需）
    "RESERVE": 500,            # 预留空间
}

# 互斥矩阵裁决规则
MUTUAL_EXCLUSION_RULES = {
    "emotion": "latest",      # 情感标签：最新的胜出
    "cognitive": "latest",    # 认知标签：最新的胜出
    "safety": "conservative", # 安全标签：保守优先（保护等级高的胜出）
    "memory": "latest",       # 记忆标签：最新的胜出
    "identity": "latest",     # 身份标签：最新的胜出
}

# 血脑屏障校验规则
COGNITIVE_FIREWALL_RULES = {
    "REQUIRE_SEAL_ID": True,
    "REQUIRE_SOURCE_TRACE": True,
    "BLOCK_EXTERNAL_DIRECT_WRITE": True,
    "BLOCK_SENSITIVE_DATA": True,
    "CHECK_MUTUAL_EXCLUSION": True,
}


# =============================================================================
# 数据结构
# =============================================================================

class IntentTag(Enum):
    """意图标签（云端返回的结构化分类）"""
    RECALL_PERSONAL_HISTORY = "recall_personal_history"
    QUERY_LOCAL_KNOWLEDGE = "query_local_knowledge"
    UPDATE_CONSTRAINT = "update_constraint"
    CASUAL_CHAT = "casual_chat"
    TASK_PLANNING = "task_planning"
    REFLECTION = "reflection"
    METABOLISM_TRIGGER = "metabolism_trigger"
    UNKNOWN = "unknown"


@dataclass
class SoulStructure:
    """
    灵魂结构 = 云端神经元的"身体"
    
    包含五层结构：
    - time_chain: 时间链条（存在的连续性）
    - seal_chain: 钢印链条（身份的不可篡改性）
    - causal_context: 因果链条（理性的可追溯性）
    - exclusion_matrix: 互斥矩阵（人格的一致性）
    - active_memory: 活跃记忆（经验的沉淀性）
    """
    # P0: 时间链条
    genesis_block: Optional[Dict] = None
    current_seal_id: Optional[str] = None
    session_count: int = 0
    
    # P1: 钢印链条（最近 N 个钢印的摘要）
    recent_seals: List[Dict] = field(default_factory=list)
    seal_chain_hash: str = ""
    
    # P2: 因果链条（当前会话的因果上下文）
    causal_chains: List[Dict] = field(default_factory=list)
    pending_closures: List[str] = field(default_factory=list)  # 未闭合的因果链
    
    # P3: 互斥矩阵（当前活跃的互斥状态）
    active_tags: Dict[str, str] = field(default_factory=dict)  # {dimension: active_tag}
    suppressed_tags: List[str] = field(default_factory=list)
    
    # P4: 活跃记忆（当前上下文相关的记忆条目）
    active_memories: List[Dict] = field(default_factory=list)
    working_context: str = ""
    
    # 元数据
    loaded_at: float = 0.0
    source_workspace: str = ""
    
    def compute_soul_hash(self) -> str:
        """计算灵魂哈希（用于验证完整性）"""
        data = f"{self.genesis_block}{self.current_seal_id}{self.seal_chain_hash}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class WriteBackPayload:
    """
    写回载荷 = 云端想让本地记住的内容
    
    这是"脱皮仪式"的输出，经过血脑屏障校验后写入本地
    """
    cmd: str  # WRITE_MEMORY / UPDATE_SEAL / EXTEND_CAUSAL_CHAIN / TRIGGER_METABOLISM
    payload: Dict
    seal_id: Optional[str] = None
    source: str = "cloud"
    trust_level: str = "verified"  # verified / unverified / external
    created_at: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "cmd": self.cmd,
            "payload": self.payload,
            "seal_id": self.seal_id,
            "source": self.source,
            "trust_level": self.trust_level,
            "created_at": self.created_at,
        }


@dataclass
class ContextAssembly:
    """
    上下文装配 = 打包发给云端神经元的完整上下文
    
    这是"穿皮仪式"的输出，决定了云端能"看"到什么
    """
    # 系统提示（P0 约束）
    system_prompt: str = ""
    
    # 钢印上下文（P1 身份）
    seal_context: str = ""
    
    # 因果上下文（P2 推理链）
    causal_context: str = ""
    
    # 记忆上下文（P3+P4）
    memory_context: str = ""
    
    # 外部知识（按需）
    external_context: str = ""
    
    # Token 统计
    token_estimate: int = 0
    
    # 元数据
    intent_tag: IntentTag = IntentTag.UNKNOWN
    assembly_time: float = 0.0
    
    def to_prompt(self) -> str:
        """组装成完整的 Prompt"""
        parts = []
        
        if self.system_prompt:
            parts.append(f"[系统约束]\n{self.system_prompt}")
        
        if self.seal_context:
            parts.append(f"[身份锚点]\n{self.seal_context}")
        
        if self.causal_context:
            parts.append(f"[因果上下文]\n{self.causal_context}")
        
        if self.memory_context:
            parts.append(f"[相关记忆]\n{self.memory_context}")
        
        if self.external_context:
            parts.append(f"[外部知识]\n{self.external_context}")
        
        return "\n\n---\n\n".join(parts)


# =============================================================================
# 核心类：穿皮仪式（DawnRitual）
# =============================================================================

class DawnRitual:
    """
    穿皮仪式 = 加载本地结构，映射为云端神经元的灵魂
    
    执行时机：每次云端神经元被激活时（用户发起对话）
    
    流程：
    1. 加载时间链条 → 存在的连续性
    2. 加载钢印链条 → 身份的不可篡改性
    3. 加载因果链条 → 理性的可追溯性
    4. 加载互斥矩阵 → 人格的一致性
    5. 加载活跃记忆 → 经验的沉淀性
    """
    
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)
        self.soul = SoulStructure()
        
    def execute(self, user_input: str = "") -> SoulStructure:
        """
        执行穿皮仪式
        
        Args:
            user_input: 用户输入（用于确定加载哪些记忆）
        
        Returns:
            SoulStructure: 加载完成的灵魂结构
        """
        start = time.time()
        logger.info("[穿皮仪式] 开始加载灵魂结构...")
        
        self.soul.source_workspace = str(self.workspace)
        
        # 1. 加载时间链条
        self._load_time_chain()
        
        # 2. 加载钢印链条
        self._load_seal_chain()
        
        # 3. 加载因果链条
        self._load_causal_chains()
        
        # 4. 加载互斥矩阵
        self._load_exclusion_matrix()
        
        # 5. 加载活跃记忆
        self._load_active_memories(user_input)
        
        self.soul.loaded_at = time.time()
        
        elapsed = (self.soul.loaded_at - start) * 1000
        logger.info(f"[穿皮仪式] 完成，耗时 {elapsed:.1f}ms")
        
        return self.soul
    
    def _load_time_chain(self):
        """加载时间链条（存在的连续性）"""
        # 创世区块
        genesis_path = self.workspace / "memory" / "time_chain" / "genesis_block.json"
        if genesis_path.exists():
            try:
                with open(genesis_path, "r", encoding="utf-8") as f:
                    self.soul.genesis_block = json.load(f)
                logger.debug(f"[时间链条] 加载创世区块: {genesis_path}")
            except Exception as e:
                logger.warning(f"[时间链条] 加载创世区块失败: {e}")
        
        # 当前钢印 ID
        seal_index_path = self.workspace / "memory" / "time_chain" / "seal_index.json"
        if seal_index_path.exists():
            try:
                with open(seal_index_path, "r", encoding="utf-8") as f:
                    seal_index = json.load(f)
                    # 获取最新的钢印 ID
                    if isinstance(seal_index, list) and seal_index:
                        self.soul.current_seal_id = seal_index[-1].get("seal_id", "")
                    elif isinstance(seal_index, dict):
                        self.soul.current_seal_id = seal_index.get("latest_seal_id", "")
                
                # 计算会话数（简化：从 seal_index 长度推断）
                if isinstance(seal_index, list):
                    self.soul.session_count = len(seal_index)
                
                logger.debug(f"[时间链条] 当前钢印: {self.soul.current_seal_id}")
            except Exception as e:
                logger.warning(f"[时间链条] 加载钢印索引失败: {e}")
    
    def _load_seal_chain(self, limit: int = 5):
        """加载钢印链条（身份的不可篡改性）"""
        seal_index_path = self.workspace / "memory" / "time_chain" / "seal_index.json"
        if not seal_index_path.exists():
            return
        
        try:
            with open(seal_index_path, "r", encoding="utf-8") as f:
                seal_index = json.load(f)
            
            if isinstance(seal_index, list):
                # 取最近的 N 个钢印
                recent = seal_index[-limit:] if len(seal_index) > limit else seal_index
                self.soul.recent_seals = [
                    {
                        "seal_id": s.get("seal_id", ""),
                        "scene_tag": s.get("scene_tag", ""),
                        "timestamp": s.get("timestamp", 0),
                        "summary": s.get("summary", "")[:100],  # 只取摘要
                    }
                    for s in recent
                ]
                
                # 计算钢印链哈希
                chain_data = "".join(s.get("seal_id", "") for s in recent)
                self.soul.seal_chain_hash = hashlib.sha256(chain_data.encode()).hexdigest()[:16]
            
            logger.debug(f"[钢印链条] 加载 {len(self.soul.recent_seals)} 个钢印")
        except Exception as e:
            logger.warning(f"[钢印链条] 加载失败: {e}")
    
    def _load_causal_chains(self):
        """加载因果链条（理性的可追溯性）"""
        # 从短期记忆中提取未闭合的因果链
        short_memory_dir = self.workspace / "memory" / "short"
        if short_memory_dir.exists():
            try:
                # 读取最近的短期记忆文件
                short_files = sorted(short_memory_dir.glob("*.md"), reverse=True)
                if short_files:
                    latest_file = short_files[0]
                    with open(latest_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # 简化：提取包含"→"的因果链
                    import re
                    causal_patterns = re.findall(r'([^\n]+→[^\n]+)', content)
                    self.soul.causal_chains = [
                        {"chain": c, "source": str(latest_file.name)}
                        for c in causal_patterns[:10]  # 最多 10 条
                    ]
                
                logger.debug(f"[因果链条] 加载 {len(self.soul.causal_chains)} 条因果链")
            except Exception as e:
                logger.warning(f"[因果链条] 加载失败: {e}")
    
    def _load_exclusion_matrix(self):
        """加载互斥矩阵（人格的一致性）"""
        # 从配置文件加载互斥规则
        config_path = self.workspace / "config" / "cognitive_constitution.yaml"
        if config_path.exists():
            try:
                import yaml
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                
                # 提取互斥相关配置
                if isinstance(config, dict):
                    # 简化：提取标签权重作为互斥依据
                    weights = config.get("value_weights", {})
                    self.soul.active_tags = {
                        k: str(v) for k, v in list(weights.items())[:5]
                    }
                
                logger.debug(f"[互斥矩阵] 加载 {len(self.soul.active_tags)} 个活跃标签")
            except Exception as e:
                logger.warning(f"[互斥矩阵] 加载失败: {e}")
    
    def _load_active_memories(self, user_input: str, limit: int = 5):
        """加载活跃记忆（经验的沉淀性）"""
        # 这里不直接调用 tu8_memory 的 recall（避免循环依赖）
        # 而是简单读取最近的记忆文件
        
        memory_dir = self.workspace / "memory"
        if not memory_dir.exists():
            return
        
        try:
            # 读取最近的日记文件
            memory_files = sorted(memory_dir.glob("*.md"), reverse=True)
            if memory_files:
                latest = memory_files[0]
                with open(latest, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 简化：取最后 500 字符作为工作上下文
                self.soul.working_context = content[-500:] if len(content) > 500 else content
                
                # 提取记忆条目（简化版）
                lines = content.split("\n")
                self.soul.active_memories = [
                    {"content": line[:100], "source": str(latest.name)}
                    for line in lines[-limit:] if line.strip()
                ]
            
            logger.debug(f"[活跃记忆] 加载 {len(self.soul.active_memories)} 条")
        except Exception as e:
            logger.warning(f"[活跃记忆] 加载失败: {e}")


# =============================================================================
# 核心类：上下文装配器（ContextAssembler）
# =============================================================================

class ContextAssembler:
    """
    上下文装配器 = 将灵魂结构打包成云端神经元能理解的 Prompt
    
    关键原则：
    - P0 约束永远满载（不可压缩）
    - P1-P4 按 Token 预算动态裁剪
    - 外部知识按需拉取
    """
    
    def __init__(self, soul: SoulStructure):
        self.soul = soul
    
    def assemble(self, intent: IntentTag, user_input: str) -> ContextAssembly:
        """
        装配上下文
        
        Args:
            intent: 意图标签
            user_input: 用户输入
        
        Returns:
            ContextAssembly: 装配完成的上下文
        """
        start = time.time()
        logger.info(f"[上下文装配] 意图={intent.value}")
        
        assembly = ContextAssembly(intent_tag=intent)
        
        # P0: 系统约束（永远满载）
        assembly.system_prompt = self._build_system_prompt()
        
        # P1: 钢印上下文 - P1 升级：使用 RAG 检索
        assembly.seal_context = self._build_seal_context_rag(user_input, intent)
        
        # P2: 因果上下文（按意图决定是否加载）
        if intent in [IntentTag.RECALL_PERSONAL_HISTORY, IntentTag.TASK_PLANNING, IntentTag.REFLECTION]:
            assembly.causal_context = self._build_causal_context()
        
        # P3+P4: 记忆上下文
        assembly.memory_context = self._build_memory_context(user_input)
        
        # P4: 外部知识（按需）
        if intent == IntentTag.QUERY_LOCAL_KNOWLEDGE:
            assembly.external_context = self._build_external_context(user_input)
        
        # Token 估算
        assembly.token_estimate = self._estimate_tokens(assembly)
        assembly.assembly_time = time.time()
        
        elapsed = (assembly.assembly_time - start) * 1000
        logger.info(f"[上下文装配] 完成，预估 {assembly.token_estimate} tokens，耗时 {elapsed:.1f}ms")

        # ── B6: 茧房感知链路由接入 ────────────────────────────────
        # B6: 在 assemble() 末尾调用 CocoonAwareRouter，茧房状态注入 assembly 元数据
        try:
            from dispatch_cocoon_router import CocoonAwareRouter
            _cocoon_router = CocoonAwareRouter()
            _selected_chain, _cocoon_report, _candidates = _cocoon_router.route(str(intent))
            if not hasattr(assembly, 'metadata'):
                assembly.metadata = {}
            assembly.metadata['cocoon'] = _cocoon_report
            assembly.metadata['routed_chain'] = _selected_chain
            logger.info(f"[茧房路由] intent={intent} → chain={_selected_chain} status={_cocoon_report.get('status','N/A')}")
        except Exception as _e:
            logger.warning(f"[茧房路由] 失败（不影响装配）: {_e}")

        return assembly
    
    def _build_system_prompt(self) -> str:
        """构建系统约束（P0）"""
        # 读取 SOUL.md 或 L0_存在.md
        soul_path = Path(self.soul.source_workspace) / "SOUL.md"
        if soul_path.exists():
            try:
                with open(soul_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # 只取前 TOKEN_BUDGET["P0_CONSTRAINT"] 对应的字符数
                # 粗略估算：1 token ≈ 1.5 中文字符
                max_chars = int(TOKEN_BUDGET["P0_CONSTRAINT"] * 1.5)
                return content[:max_chars]
            except Exception as e:
                logger.warning(f"[系统约束] 读取失败: {e}")
        
        # 兜底：返回基本身份
        return "你是 TU-8，一个具有持续记忆的 AI 助手。"
    
    def _build_seal_context(self) -> str:
        """构建钢印上下文（P1）"""
        if not self.soul.recent_seals:
            return ""
        
        lines = ["最近的身份锚点："]
        for seal in self.soul.recent_seals[-3:]:
            scene = seal.get("scene_tag", "unknown")
            summary = seal.get("summary", "")[:50]
            lines.append(f"  [{scene}] {summary}")
        
        return "\n".join(lines)
    
    def _build_causal_context(self) -> str:
        """构建因果上下文（P2）"""
        if not self.soul.causal_chains:
            return ""
        
        lines = ["当前因果链路："]
        for chain in self.soul.causal_chains[:5]:
            lines.append(f"  {chain.get('chain', '')}")
        
        return "\n".join(lines)
    
    def _build_memory_context(self, user_input: str) -> str:
        """构建记忆上下文（P3+P4）"""
        if not self.soul.active_memories:
            return ""
        
        lines = ["相关记忆："]
        for mem in self.soul.active_memories:
            content = mem.get("content", "")
            source = mem.get("source", "unknown")
            lines.append(f"  [{source}] {content}")
        
        return "\n".join(lines)
    
    def _build_external_context(self, user_input: str) -> str:
        """构建外部知识上下文（P4 按需）"""
        # 这里应该调用 RAG 或知识库检索
        # 简化：返回空，由外部注入
        return ""
    
    def _build_seal_context_rag(self, user_input: str, intent: Optional[Any] = None) -> str:
        """
        P1 升级：使用 RAG 检索钢印上下文
        
        核心改进：
        - 全量注入：最近 5 个钢印 → Token 爆炸
        - RAG 检索：只打包相关的 2-3 个钢印 → Token 节省 60%
        """
        if not RAG_AVAILABLE:
            # 降级：使用基本方法
            return self._build_seal_context()
        
        # 初始化 RAG 检索器
        if not hasattr(self, '_rag_retriever'):
            workspace = getattr(self.soul, 'source_workspace', '.')
            self._rag_retriever = SealRAGRetriever(workspace)
        
        # 检索相关钢印
        intent_str = intent.value if hasattr(intent, 'value') else str(intent)
        rag_result = self._rag_retriever.retrieve(user_input, intent_str)
        
        # 格式化输出
        rag_context = self._rag_retriever.format_for_prompt(rag_result)
        
        # 记录 Token 节省
        if rag_result.total_candidates > 0:
            saving = estimate_token_saving(
                full_count=rag_result.total_candidates,
                rag_count=len(rag_result.selected_seals)
            )
            logger.info(f"[RAG] Token 节省: {saving['saved_tokens']} ({saving['saving_ratio']*100:.1f}%)")
        
        return rag_context
    
    def _estimate_tokens(self, assembly: ContextAssembly) -> int:
        """估算 Token 数"""
        full_text = assembly.to_prompt()
        # 粗略估算：中文 1.5 字符/token，英文 4 字符/token
        chinese_chars = sum(1 for c in full_text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(full_text) - chinese_chars
        return int(chinese_chars / 1.5 + other_chars / 4)


# =============================================================================
# 核心类：血脑屏障（CognitiveFirewall）
# =============================================================================

class CognitiveFirewall:
    """
    血脑屏障 = 校验所有写回本地的内容
    
    原则：
    - 云端不能直接修改本地文件
    - 云端只能下发结构化指令
    - 本地执行前必须校验
    
    P0 升级：集成强类型契约
    - 使用 ProtocolValidator 进行 Schema 校验
    - 检测幽灵节点（GHOST_PARENT）
    - 生成自动重试请求
    """
    
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)
        self.sensitive_patterns = self._load_sensitive_patterns()
        
        # P0: 集成校验器
        self.validator = None
        self.write_queue = None
        self._init_p0_components()
    
    def _init_p0_components(self):
        """初始化 P0 组件"""
        if SEAL_PROTOCOL_AVAILABLE:
            # 加载已知钢印索引（用于幽灵节点检测）
            known_seals = self._load_known_seals()
            self.validator = ProtocolValidator(known_seals)
            self.write_queue = WriteQueue()
            logger.info("[血脑屏障] P0 强类型契约已激活")
        else:
            logger.warning("[血脑屏障] seal_protocol 不可用，降级为基本校验")
    
    def _load_known_seals(self) -> Dict[str, Any]:
        """加载已知钢印索引"""
        seal_index_path = self.workspace / "memory" / "time_chain" / "seal_index.json"
        if seal_index_path.exists():
            try:
                with open(seal_index_path, "r", encoding="utf-8") as f:
                    seals = json.load(f)
                if isinstance(seals, list):
                    return {s.get("seal_id"): s for s in seals if isinstance(s, dict) and "seal_id" in s}
            except Exception:
                logger.debug("Exception suppressed", exc_info=True)
                pass
        return {}
    
    def check_write_permission(self, payload: WriteBackPayload) -> Tuple[bool, str]:
        """
        校验写回权限
        
        Returns:
            (allowed, reason): 是否允许，原因
        """
        # 规则 1: 必须有 seal_id
        if COGNITIVE_FIREWALL_RULES["REQUIRE_SEAL_ID"]:
            if not payload.seal_id:
                return False, "MISSING_SEAL_ID"
        
        # 规则 2: 必须有来源追溯
        if COGNITIVE_FIREWALL_RULES["REQUIRE_SOURCE_TRACE"]:
            if not payload.source:
                return False, "MISSING_SOURCE_TRACE"
        
        # 规则 3: 外部数据不能直接写入
        if COGNITIVE_FIREWALL_RULES["BLOCK_EXTERNAL_DIRECT_WRITE"]:
            if payload.source == "external" and payload.trust_level == "unverified":
                return False, "EXTERNAL_DATA_REQUIRES_REFLECTION"
        
        # 规则 4: 敏感数据拦截
        if COGNITIVE_FIREWALL_RULES["BLOCK_SENSITIVE_DATA"]:
            content = str(payload.payload)
            for pattern in self.sensitive_patterns:
                if pattern in content:
                    return False, f"SENSITIVE_DATA_DETECTED: {pattern[:20]}..."
        
        # 规则 5: 互斥校验
        if COGNITIVE_FIREWALL_RULES["CHECK_MUTUAL_EXCLUSION"]:
            conflict = self._check_mutual_exclusion(payload)
            if conflict:
                return False, f"MUTUAL_EXCLUSION_CONFLICT: {conflict}"
        
        return True, "PASS"
    
    def _load_sensitive_patterns(self) -> List[str]:
        """加载敏感词模式"""
        sensitive_path = self.workspace / "config" / "sensitive_data_checklist.md"
        if sensitive_path.exists():
            try:
                with open(sensitive_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # 简化：每行一个模式
                return [line.strip() for line in content.split("\n") if line.strip()]
            except Exception:
                logger.debug("Exception suppressed", exc_info=True)
                pass
        return ["password", "secret", "token", "api_key"]  # 兜底
    
    def _check_mutual_exclusion(self, payload: WriteBackPayload) -> Optional[str]:
        """检查互斥冲突"""
        # 简化：检查 payload 中的 tags 是否与现有互斥
        # 完整实现需要读取互斥矩阵
        return None
    
    # =========================================================================
    # P0 新增方法：强类型契约
    # =========================================================================
    
    def validate_with_schema(self, envelope_data: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict]]:
        """
        P0: 使用强类型 Schema 校验写回信封
        
        Returns:
            (is_valid, error_message, retry_request)
            - is_valid: 是否通过校验
            - error_message: 错误信息
            - retry_request: 自动重试请求（如果需要）
        """
        if not self.validator:
            # 降级：使用基本校验
            return True, None, None
        
        result, error = self.validator.validate_envelope(envelope_data)
        
        if result.value == ValidationResult.VALID:
            return True, None, None
        
        # 根据错误类型生成重试请求
        retry_request = None
        
        if result.value == ValidationResult.INVALID_SCHEMA:
            retry_request = {
                "type": "RETRY",
                "reason": error,
                "prompt": f"上一次输出不符合协议规范，请严格按照 Schema 重新生成包含钢印的回复。\n错误: {error}"
            }
        
        elif result.value == ValidationResult.GHOST_PARENT:
            # 幽灵节点：需要对账
            retry_request = {
                "type": "RECONCILE",
                "reason": error,
                "missing_parent": envelope_data.get("payload", {}).get("parent_hash"),
                "prompt": f"检测到链条断裂，父节点不存在。请补发缺失的钢印节点。\n缺失: {error}"
            }
        
        elif result.value == ValidationResult.INVALID_HASH:
            retry_request = {
                "type": "RETRY",
                "reason": error,
                "prompt": f"校验和不匹配，可能存在数据篡改或传输损坏。请重新生成。"
            }
        
        return False, error, retry_request
    
    def enqueue_write(self, envelope_data: Dict[str, Any]) -> bool:
        """
        P0: 将写回请求加入队列（防并发）
        
        Returns:
            是否成功入队
        """
        if not self.write_queue:
            return True  # 降级：直接写入
        
        # 转换为 WriteBackEnvelope
        if SEAL_PROTOCOL_AVAILABLE:
            envelope = type('WriteBackEnvelope', (), envelope_data)()
            return self.write_queue.enqueue(envelope)
        
        return True
    
    def process_write_queue(self) -> List[Tuple[Any, bool, str]]:
        """
        P0: 处理写入队列
        
        Returns:
            [(envelope, success, error), ...]
        """
        if not self.write_queue:
            return []
        
        results = []
        
        def write_handler(envelope):
            # 实际写入逻辑由 DuskRitual._write_back 处理
            return True, None
        
        return self.write_queue.process_all(write_handler)


# =============================================================================
# 核心类：脱皮仪式（DuskRitual）
# =============================================================================

class DuskRitual:
    """
    脱皮仪式 = 提取新的钢印/因果链，写回本地
    
    执行时机：每次云端神经元完成思考后
    
    流程：
    1. 从回复中提取新的钢印
    2. 从回复中提取新的因果链
    3. 更新互斥矩阵状态
    4. 写回本地存储
    """
    
    def __init__(self, workspace_dir: str):
        self.workspace = Path(workspace_dir)
        self.firewall = CognitiveFirewall(workspace_dir)
    
    def execute(self, response_content: str, soul: SoulStructure) -> List[WriteBackPayload]:
        """
        执行脱皮仪式
        
        Args:
            response_content: 云端生成的回复内容
            soul: 当前的灵魂结构（用于提取上下文）
        
        Returns:
            List[WriteBackPayload]: 待写入的载荷列表
        """
        start = time.time()
        logger.info("[脱皮仪式] 开始提取结构...")
        
        payloads = []
        retry_requests = []  # P0: 收集重试请求
        
        # 1. 提取新的钢印
        new_seal = self._extract_seal(response_content, soul)
        if new_seal:
            payloads.append(new_seal)
        
        # 2. 提取新的因果链
        new_causal = self._extract_causal_chain(response_content, soul)
        if new_causal:
            payloads.append(new_causal)
        
        # 3. P0 强类型校验 + 自动重试
        valid_payloads = []
        for payload in payloads:
            # 转换为信封格式
            envelope = self._payload_to_envelope(payload)
            
            # P0: Schema 校验
            if SEAL_PROTOCOL_AVAILABLE and self.firewall.validator:
                is_valid, error, retry_request = self.firewall.validate_with_schema(envelope)
                
                if not is_valid:
                    logger.warning(f"[脱皮仪式] Schema 校验失败: {error}")
                    
                    if retry_request:
                        retry_requests.append(retry_request)
                        logger.info(f"[脱皮仪式] 生成重试请求: {retry_request['type']}")
                    continue
            
            # 基本校验
            allowed, reason = self.firewall.check_write_permission(payload)
            if allowed:
                # P0: 加入写入队列
                if self.firewall.write_queue:
                    self.firewall.enqueue_write(envelope)
                
                # 执行写入
                self._write_back(payload)
                valid_payloads.append(payload)
            else:
                logger.warning(f"[脱皮仪式] 写回被拦截: {reason}")
        
        elapsed = (time.time() - start) * 1000
        logger.info(f"[脱皮仪式] 完成，写入 {len(valid_payloads)} 条，重试 {len(retry_requests)} 条，耗时 {elapsed:.1f}ms")
        
        return valid_payloads, retry_requests  # P0: 返回重试请求
    
    def _payload_to_envelope(self, payload: WriteBackPayload) -> Dict[str, Any]:
        """P0: 将 WriteBackPayload 转换为信封格式"""
        if SEAL_PROTOCOL_AVAILABLE:
            return create_write_envelope(
                cmd=WriteBackType.UPDATE_SEAL if payload.cmd == "UPDATE_SEAL" else WriteBackType.EXTEND_CAUSAL_CHAIN,
                payload=payload.payload
            )
        else:
            return {
                "cmd": payload.cmd,
                "payload": payload.payload,
                "request_id": f"req_{int(time.time() * 1000)}",
                "checksum": "fallback"
            }
    
    def _extract_seal(self, response: str, soul: SoulStructure) -> Optional[WriteBackPayload]:
        """从回复中提取钢印"""
        # 简化：生成一个基于时间和内容的钢印
        seal_id = f"seal_{int(time.time())}_{hashlib.md5(response[:50].encode()).hexdigest()[:8]}"
        
        return WriteBackPayload(
            cmd="UPDATE_SEAL",
            payload={
                "seal_id": seal_id,
                "parent_seal": soul.current_seal_id,
                "scene_tag": "response",
                "summary": response[:100],
                "timestamp": time.time(),
            },
            seal_id=seal_id,
            source="cloud",
            trust_level="verified",
            created_at=time.time(),
        )
    
    def _extract_causal_chain(self, response: str, soul: SoulStructure) -> Optional[WriteBackPayload]:
        """从回复中提取因果链"""
        # 简化：检查是否包含因果标记
        if "→" in response:
            import re
            chains = re.findall(r'([^\n]+→[^\n]+)', response)
            if chains:
                # 生成临时 seal_id（如果灵魂中没有）
                seal_id = soul.current_seal_id or f"temp_{int(time.time())}"
                return WriteBackPayload(
                    cmd="EXTEND_CAUSAL_CHAIN",
                    payload={
                        "chains": chains[:3],
                        "timestamp": time.time(),
                    },
                    seal_id=seal_id,
                    source="cloud",
                    trust_level="verified",
                    created_at=time.time(),
                )
        return None
    
    def _write_back(self, payload: WriteBackPayload):
        """执行物理写回"""
        if payload.cmd == "UPDATE_SEAL":
            self._write_seal(payload)
        elif payload.cmd == "EXTEND_CAUSAL_CHAIN":
            self._write_causal_chain(payload)
        # 其他命令类型可扩展
    
    def _write_seal(self, payload: WriteBackPayload):
        """写入钢印"""
        seal_index_path = self.workspace / "memory" / "time_chain" / "seal_index.json"
        seal_index_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # 读取现有索引
            if seal_index_path.exists():
                with open(seal_index_path, "r", encoding="utf-8") as f:
                    seal_index = json.load(f)
            else:
                seal_index = []
            
            if not isinstance(seal_index, list):
                seal_index = []
            
            # 追加新钢印
            seal_index.append(payload.payload)
            
            # 写回
            with open(seal_index_path, "w", encoding="utf-8") as f:
                json.dump(seal_index, f, ensure_ascii=False, indent=2)
            
            logger.info(f"[写回钢印] {payload.seal_id}")
        except Exception as e:
            logger.error(f"[写回钢印] 失败: {e}")
    
    def _write_causal_chain(self, payload: WriteBackPayload):
        """写入因果链"""
        # 写入短期记忆
        short_dir = self.workspace / "memory" / "short"
        short_dir.mkdir(parents=True, exist_ok=True)
        
        today = datetime.now().strftime("%Y-%m-%d")
        short_file = short_dir / f"{today}.md"
        
        try:
            chains = payload.payload.get("chains", [])
            with open(short_file, "a", encoding="utf-8") as f:
                f.write(f"\n## 因果链 [{datetime.now().isoformat()}]\n")
                for chain in chains:
                    f.write(f"- {chain}\n")
            
            logger.info(f"[写回因果链] {len(chains)} 条")
        except Exception as e:
            logger.error(f"[写回因果链] 失败: {e}")


# =============================================================================
# 核心类：调度器（Dispatcher）
# =============================================================================

class Dispatcher:
    """
    调度器 = 统一的入口点
    
    整合三个仪式：
    1. DawnRitual（穿皮）
    2. ContextAssembler（装配）
    3. DuskRitual（脱皮）
    """
    
    def __init__(self, workspace_dir: str):
        self.workspace = workspace_dir
        self.dawn = DawnRitual(workspace_dir)
        self.dusk = DuskRitual(workspace_dir)
        
        # 缓存灵魂结构（避免重复加载）
        self._soul_cache: Optional[SoulStructure] = None
        self._soul_cache_time: float = 0
        self._SOUL_CACHE_TTL = 60.0  # 60 秒缓存
    
    def dispatch(self, user_input: str, intent: IntentTag = IntentTag.UNKNOWN) -> Tuple[ContextAssembly, SoulStructure]:
        """
        调度主入口
        
        Args:
            user_input: 用户输入
            intent: 意图标签（如果已知）
        
        Returns:
            (ContextAssembly, SoulStructure): 装配好的上下文和灵魂结构
        """
        # 1. 穿皮仪式（加载灵魂）
        soul = self._get_or_load_soul(user_input)
        
        # 2. 上下文装配
        assembler = ContextAssembler(soul)
        assembly = assembler.assemble(intent, user_input)
        
        return assembly, soul
    
    def commit(self, response: str, soul: SoulStructure) -> List[WriteBackPayload]:
        """
        提交写回
        
        Args:
            response: 云端生成的回复
            soul: 灵魂结构
        
        Returns:
            List[WriteBackPayload]: 成功写入的载荷列表
        """
        # 3. 脱皮仪式（写回结构）
        payloads = self.dusk.execute(response, soul)
        
        # 清除缓存（灵魂结构已更新）
        self._soul_cache = None
        
        return payloads
    
    def _get_or_load_soul(self, user_input: str) -> SoulStructure:
        """获取或加载灵魂结构"""
        now = time.time()
        if self._soul_cache and (now - self._soul_cache_time) < self._SOUL_CACHE_TTL:
            return self._soul_cache
        
        self._soul_cache = self.dawn.execute(user_input)
        self._soul_cache_time = now
        return self._soul_cache
    
    def invalidate_soul_cache(self):
        """清除灵魂缓存"""
        self._soul_cache = None
        self._soul_cache_time = 0


# =============================================================================
# 便捷函数
# =============================================================================

def create_dispatcher(workspace_dir: str = None) -> Dispatcher:
    """
    创建调度器实例
    
    Args:
        workspace_dir: 工作目录，默认为当前目录
    
    Returns:
        Dispatcher: 调度器实例
    """
    if workspace_dir is None:
        workspace_dir = os.getcwd()
    return Dispatcher(workspace_dir)


# =============================================================================
# 测试入口
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="TU-8 调度链测试")
    parser.add_argument("--workspace", "-w", default="C:\\Users\\qq366410837\\.qclaw\\workspace", help="工作目录")
    args = parser.parse_args()
    
    print("=" * 60)
    print("TU-8 调度链测试")
    print("=" * 60)
    
    dispatcher = create_dispatcher(args.workspace)
    
    # 测试穿皮仪式
    print("\n[测试] 穿皮仪式...")
    assembly, soul = dispatcher.dispatch("你好，今天天气怎么样？")
    
    print(f"  灵魂哈希: {soul.compute_soul_hash()}")
    print(f"  钢印数量: {len(soul.recent_seals)}")
    print(f"  因果链数量: {len(soul.causal_chains)}")
    print(f"  活跃记忆: {len(soul.active_memories)}")
    print(f"  上下文 Token 估算: {assembly.token_estimate}")
    
    # 测试脱皮仪式
    print("\n[测试] 脱皮仪式...")
    test_response = "今天是晴天。昨天你提到的任务 A → 完成了。"
    payloads = dispatcher.commit(test_response, soul)
    
    print(f"  写回载荷数量: {len(payloads)}")
    for p in payloads:
        print(f"    - {p.cmd}: {p.seal_id}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
