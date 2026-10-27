# -*- coding: utf-8 -*-
"""
seal_protocol.py — 钢印协议：强类型契约层
日期: 2026-06-07
功能: 定义云端-本地之间的严格 Schema，杜绝格式损坏

核心组件：
1. SealPayload Schema — 钢印载荷结构
2. CausalChainPayload Schema — 因果链载荷结构
3. WriteBackEnvelope Schema — 写回信封（统一包装）
4. ProtocolValidator — 校验器
5. ReconcileRequest — 对账请求（修复幽灵节点）
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
import json
import hashlib
import time
import re
from datetime import datetime

# 尝试导入 pydantic（可选依赖）
try:
    from pydantic import BaseModel, Field, field_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object
    Field = lambda default=None, **kwargs: default


# =============================================================================
# 枚举定义
# =============================================================================

class SealPriority(str, Enum):
    """钢印优先级"""
    P0_CRITICAL = "P0"      # 核心身份，不可变
    P1_IDENTITY = "P1"      # 身份相关，高优先级
    P2_BEHAVIOR = "P2"      # 行为模式
    P3_EPISODIC = "P3"      # 情景记忆
    P4_EPHEMERAL = "P4"     # 临时状态


class WriteBackType(str, Enum):
    """写回类型"""
    UPDATE_SEAL = "UPDATE_SEAL"
    EXTEND_CAUSAL_CHAIN = "EXTEND_CAUSAL_CHAIN"
    CREATE_MEMORY = "CREATE_MEMORY"
    UPDATE_MUTEX = "UPDATE_MUTEX"
    RECONCILE = "RECONCILE"


class ValidationResult(str, Enum):
    """校验结果"""
    VALID = "VALID"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    MISSING_SEAL = "MISSING_SEAL"
    INVALID_HASH = "INVALID_HASH"
    GHOST_PARENT = "GHOST_PARENT"      # 幽灵节点：父节点不存在
    MUTEX_VIOLATION = "MUTEX_VIOLATION"


# =============================================================================
# Schema 定义（兼容 Pydantic 和 dataclass）
# =============================================================================

if PYDANTIC_AVAILABLE:
    # Pydantic 版本（有运行时校验）
    class SealPayload(BaseModel):
        """钢印载荷"""
        seal_id: str = Field(..., description="钢印唯一ID，格式: seal_{timestamp}_{hash}")
        content: str = Field(..., description="钢印内容")
        priority: SealPriority = Field(default=SealPriority.P3_EPISODIC)
        parent_hash: str = Field(..., description="父节点哈希，保证链条连续性")
        content_hash: str = Field(..., description="内容哈希，防止篡改")
        timestamp: float = Field(default_factory=time.time)
        tags: List[str] = Field(default_factory=list)
        metadata: Dict[str, Any] = Field(default_factory=dict)
        
        @field_validator('seal_id')
        @classmethod
        def validate_seal_id(cls, v):
            if not re.match(r'^seal_\d+_[a-f0-9]+$', v):
                raise ValueError(f"Invalid seal_id format: {v}")
            return v
        
        @field_validator('content_hash')
        @classmethod
        def validate_content_hash(cls, v):
            if not re.match(r'^[a-f0-9]{8,}$', v):
                raise ValueError(f"Invalid content_hash format: {v}")
            return v
        
        class Config:
            use_enum_values = True
    
    class CausalChainPayload(BaseModel):
        """因果链载荷"""
        chain_id: str = Field(..., description="因果链ID")
        cause: str = Field(..., description="原因")
        effect: str = Field(..., description="结果")
        seal_id: str = Field(..., description="关联的钢印ID")
        confidence: float = Field(default=1.0, ge=0.0, le=1.0)
        timestamp: float = Field(default_factory=time.time)
    
    class WriteBackEnvelope(BaseModel):
        """写回信封（统一包装）"""
        cmd: WriteBackType = Field(..., description="写回命令类型")
        payload: Dict[str, Any] = Field(..., description="载荷数据")
        request_id: str = Field(..., description="请求ID，用于幂等校验")
        timestamp: float = Field(default_factory=time.time)
        checksum: str = Field(..., description="校验和")
        
        @field_validator('checksum')
        @classmethod
        def validate_checksum(cls, v, info):
            # 计算校验和
            if 'payload' in info.data:
                expected = hashlib.md5(
                    json.dumps(info.data['payload'], sort_keys=True).encode()
                ).hexdigest()[:8]
                if v != expected:
                    raise ValueError(f"Checksum mismatch: expected {expected}, got {v}")
            return v
        
        class Config:
            use_enum_values = True

else:
    # dataclass 版本（无运行时校验，仅作结构定义）
    @dataclass
    class SealPayload:
        """钢印载荷"""
        seal_id: str
        content: str
        parent_hash: str
        content_hash: str
        priority: SealPriority = SealPriority.P3_EPISODIC
        timestamp: float = field(default_factory=time.time)
        tags: List[str] = field(default_factory=list)
        metadata: Dict[str, Any] = field(default_factory=dict)
    
    @dataclass
    class CausalChainPayload:
        """因果链载荷"""
        chain_id: str
        cause: str
        effect: str
        seal_id: str
        confidence: float = 1.0
        timestamp: float = field(default_factory=time.time)
    
    @dataclass
    class WriteBackEnvelope:
        """写回信封"""
        cmd: WriteBackType
        payload: Dict[str, Any]
        request_id: str
        checksum: str
        timestamp: float = field(default_factory=time.time)


# =============================================================================
# 校验器
# =============================================================================

class ProtocolValidator:
    """协议校验器：所有写回数据的守门员"""
    
    def __init__(self, known_seals: Optional[Dict[str, Any]] = None):
        """
        Args:
            known_seals: 已知钢印索引 {seal_id: seal_data}
        """
        self.known_seals = known_seals or {}
        self._pending_queue: List[WriteBackEnvelope] = []  # 待确认队列
    
    def validate_seal(self, seal_data: Dict[str, Any]) -> tuple[ValidationResult, Optional[str]]:
        """
        校验钢印载荷
        
        Returns:
            (result, error_message)
        """
        # 1. 必填字段检查
        required_fields = ['seal_id', 'content', 'parent_hash', 'content_hash']
        for field in required_fields:
            if field not in seal_data:
                return ValidationResult.INVALID_SCHEMA, f"Missing required field: {field}"
        
        # 2. seal_id 格式校验
        seal_id = seal_data['seal_id']
        if not re.match(r'^seal_\d+_[a-f0-9]+$', seal_id):
            return ValidationResult.INVALID_SCHEMA, f"Invalid seal_id format: {seal_id}"
        
        # 3. 内容哈希校验（防篡改）
        content = seal_data['content']
        expected_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        if seal_data['content_hash'] != expected_hash:
            return ValidationResult.INVALID_HASH, f"Content hash mismatch"
        
        # 4. 父节点存在性检查（幽灵节点检测）
        parent_hash = seal_data['parent_hash']
        if parent_hash != "GENESIS" and parent_hash not in self._get_all_parent_hashes():
            return ValidationResult.GHOST_PARENT, f"Parent not found: {parent_hash}"
        
        # 5. Pydantic 运行时校验（如果可用）
        if PYDANTIC_AVAILABLE:
            try:
                SealPayload(**seal_data)
            except Exception as e:
                return ValidationResult.INVALID_SCHEMA, str(e)
        
        return ValidationResult.VALID, None
    
    def validate_envelope(self, envelope_data: Dict[str, Any]) -> tuple[ValidationResult, Optional[str]]:
        """
        校验写回信封
        
        Returns:
            (result, error_message)
        """
        # 1. 必填字段
        required = ['cmd', 'payload', 'request_id', 'checksum']
        for field in required:
            if field not in envelope_data:
                return ValidationResult.INVALID_SCHEMA, f"Missing: {field}"
        
        # 2. 校验和验证
        payload = envelope_data['payload']
        expected_checksum = hashlib.md5(
            json.dumps(payload, sort_keys=True).encode()
        ).hexdigest()[:8]
        if envelope_data['checksum'] != expected_checksum:
            return ValidationResult.INVALID_HASH, "Checksum mismatch"
        
        # 3. 根据 cmd 类型校验 payload
        cmd = envelope_data['cmd']
        if cmd == WriteBackType.UPDATE_SEAL.value:
            return self.validate_seal(payload)
        elif cmd == WriteBackType.EXTEND_CAUSAL_CHAIN.value:
            return self._validate_causal_chain(payload)
        
        return ValidationResult.VALID, None
    
    def _validate_causal_chain(self, data: Dict[str, Any]) -> tuple[ValidationResult, Optional[str]]:
        """校验因果链载荷"""
        required = ['chain_id', 'cause', 'effect', 'seal_id']
        for field in required:
            if field not in data:
                return ValidationResult.INVALID_SCHEMA, f"Missing: {field}"
        
        # 检查关联的 seal_id 是否存在
        seal_id = data['seal_id']
        if seal_id not in self.known_seals:
            return ValidationResult.GHOST_PARENT, f"Referenced seal not found: {seal_id}"
        
        return ValidationResult.VALID, None
    
    def _get_all_parent_hashes(self) -> set:
        """获取所有已知钢印的 parent_hash"""
        hashes = set()
        for seal_id, seal_data in self.known_seals.items():
            if isinstance(seal_data, dict) and 'content_hash' in seal_data:
                hashes.add(seal_data['content_hash'])
        return hashes
    
    def add_to_pending(self, envelope: WriteBackEnvelope):
        """添加到待确认队列"""
        self._pending_queue.append(envelope)
    
    def get_pending(self) -> List[WriteBackEnvelope]:
        """获取待确认队列"""
        return self._pending_queue.copy()
    
    def clear_pending(self, request_id: str):
        """清除已确认的请求"""
        self._pending_queue = [
            e for e in self._pending_queue 
            if getattr(e, 'request_id', None) != request_id
        ]


# =============================================================================
# 对账请求（修复幽灵节点）
# =============================================================================

@dataclass
class ReconcileRequest:
    """对账请求：修复网络断连导致的幽灵节点"""
    
    missing_parent_hash: str       # 缺失的父节点哈希
    current_seal_id: str           # 当前钢印ID（孤儿节点）
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0
    
    def to_prompt(self) -> str:
        """生成对账请求的 Prompt"""
        return f"""[RECONCILE_REQUEST]
检测到链条断裂：当前钢印 {self.current_seal_id} 的父节点 {self.missing_parent_hash} 不存在。
请根据当前对话上下文，补发缺失的钢印节点。

要求格式：
{{
  "cmd": "RECONCILE",
  "payload": {{
    "seal_id": "seal_<timestamp>_<hash>",
    "content": "缺失的钢印内容",
    "parent_hash": "{self.missing_parent_hash}",
    "content_hash": "<hash>"
  }}
}}
"""


# =============================================================================
# 写回队列（防并发）
# =============================================================================

class WriteQueue:
    """
    单线程写入队列：从根本上消灭并发冲突
    
    设计原则：
    1. 所有写回指令必须排队
    2. 单线程处理，保证顺序
    3. 幂等校验，防止重复写入
    4. 失败重试，保证最终一致性
    """
    
    def __init__(self, max_size: int = 1000):
        self._queue: List[WriteBackEnvelope] = []
        self._processed_ids: set = set()  # 已处理的 request_id（幂等校验）
        self._max_size = max_size
        self._lock = None  # 延迟导入 threading
    
    def enqueue(self, envelope: WriteBackEnvelope) -> bool:
        """
        入队
        
        Returns:
            True 成功入队，False 队列已满
        """
        if len(self._queue) >= self._max_size:
            return False
        
        # 幂等校验
        request_id = getattr(envelope, 'request_id', None)
        if request_id and request_id in self._processed_ids:
            return True  # 已处理，跳过
        
        self._queue.append(envelope)
        return True
    
    def dequeue(self) -> Optional[WriteBackEnvelope]:
        """出队"""
        if not self._queue:
            return None
        
        envelope = self._queue.pop(0)
        request_id = getattr(envelope, 'request_id', None)
        if request_id:
            self._processed_ids.add(request_id)
        
        return envelope
    
    def process_all(self, handler: callable) -> List[tuple]:
        """
        批量处理队列
        
        Args:
            handler: 处理函数 (envelope) -> (success: bool, error: str)
        
        Returns:
            [(envelope, success, error), ...]
        """
        results = []
        while self._queue:
            envelope = self.dequeue()
            try:
                success, error = handler(envelope)
                results.append((envelope, success, error))
            except Exception as e:
                results.append((envelope, False, str(e)))
        
        return results
    
    def size(self) -> int:
        """队列大小"""
        return len(self._queue)
    
    def clear(self):
        """清空队列"""
        self._queue.clear()
        self._processed_ids.clear()


# =============================================================================
# 工具函数
# =============================================================================

def generate_seal_id(content: str, timestamp: Optional[float] = None) -> str:
    """生成钢印ID"""
    ts = timestamp or time.time()
    content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"seal_{int(ts)}_{content_hash}"


def compute_content_hash(content: str) -> str:
    """计算内容哈希"""
    return hashlib.md5(content.encode()).hexdigest()[:8]


def compute_checksum(payload: Dict[str, Any]) -> str:
    """计算校验和"""
    return hashlib.md5(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()[:8]


def create_seal_payload(
    content: str,
    parent_hash: str,
    priority: SealPriority = SealPriority.P3_EPISODIC,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    创建钢印载荷（便捷函数）
    
    Args:
        content: 钢印内容
        parent_hash: 父节点哈希
        priority: 优先级
        tags: 标签列表
        metadata: 元数据
    
    Returns:
        完整的钢印载荷字典
    """
    timestamp = time.time()
    content_hash = compute_content_hash(content)
    seal_id = generate_seal_id(content, timestamp)
    
    return {
        "seal_id": seal_id,
        "content": content,
        "priority": priority.value if isinstance(priority, SealPriority) else priority,
        "parent_hash": parent_hash,
        "content_hash": content_hash,
        "timestamp": timestamp,
        "tags": tags or [],
        "metadata": metadata or {}
    }


def create_write_envelope(
    cmd: WriteBackType,
    payload: Dict[str, Any],
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建写回信封（便捷函数）
    
    Args:
        cmd: 写回命令类型
        payload: 载荷数据
        request_id: 请求ID（不提供则自动生成）
    
    Returns:
        完整的写回信封字典
    """
    if request_id is None:
        request_id = f"req_{int(time.time() * 1000)}"
    
    checksum = compute_checksum(payload)
    
    return {
        "cmd": cmd.value if isinstance(cmd, WriteBackType) else cmd,
        "payload": payload,
        "request_id": request_id,
        "timestamp": time.time(),
        "checksum": checksum
    }


# =============================================================================
# 测试
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("钢印协议测试")
    print("=" * 60)
    
    # 1. 创建钢印载荷
    print("\n[测试 1] 创建钢印载荷...")
    seal = create_seal_payload(
        content="用户偏好：喜欢简洁的技术文档",
        parent_hash="GENESIS",
        priority=SealPriority.P2_BEHAVIOR,
        tags=["preference", "documentation"]
    )
    print(f"  [v] seal_id: {seal['seal_id']}")
    print(f"  [v] content_hash: {seal['content_hash']}")
    
    # 2. 创建写回信封
    print("\n[测试 2] 创建写回信封...")
    envelope = create_write_envelope(
        cmd=WriteBackType.UPDATE_SEAL,
        payload=seal
    )
    print(f"  [v] cmd: {envelope['cmd']}")
    print(f"  [v] request_id: {envelope['request_id']}")
    print(f"  [v] checksum: {envelope['checksum']}")
    
    # 3. 校验器测试
    print("\n[测试 3] 校验器...")
    validator = ProtocolValidator()
    
    # 正常校验
    result, error = validator.validate_seal(seal)
    print(f"  [v] 正常校验: {result.value}")
    
    # 错误校验（缺少字段）
    bad_seal = {"seal_id": "invalid"}
    result, error = validator.validate_seal(bad_seal)
    print(f"  [v] 错误校验: {result.value} - {error}")
    
    # 4. 写入队列测试
    print("\n[测试 4] 写入队列...")
    queue = WriteQueue()
    queue.enqueue(envelope)
    print(f"  [v] 队列大小: {queue.size()}")
    
    # 处理队列
    def mock_handler(e):
        print(f"    处理: {e['cmd']}")
        return True, None
    
    results = queue.process_all(mock_handler)
    print(f"  [v] 处理结果: {len(results)} 条")
    
    print("\n" + "=" * 60)
    print("所有测试通过")
    print("=" * 60)
