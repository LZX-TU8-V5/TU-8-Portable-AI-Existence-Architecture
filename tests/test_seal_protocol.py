# -*- coding: utf-8 -*-
"""测试钢印协议"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# 强制 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from seal_protocol import (
    create_seal_payload,
    create_write_envelope,
    ProtocolValidator,
    WriteQueue,
    WriteBackType,
    SealPriority
)

print("=" * 60)
print("Seal Protocol Test")
print("=" * 60)

# 1. 创建钢印载荷
print("\n[Test 1] Create seal payload...")
seal = create_seal_payload(
    content="User preference: likes concise technical docs",
    parent_hash="GENESIS",
    priority=SealPriority.P2_BEHAVIOR,
    tags=["preference", "documentation"]
)
print(f"  OK seal_id: {seal['seal_id']}")
print(f"  OK content_hash: {seal['content_hash']}")

# 2. 创建写回信封
print("\n[Test 2] Create write envelope...")
envelope = create_write_envelope(
    cmd=WriteBackType.UPDATE_SEAL,
    payload=seal
)
print(f"  OK cmd: {envelope['cmd']}")
print(f"  OK request_id: {envelope['request_id']}")
print(f"  OK checksum: {envelope['checksum']}")

# 3. 校验器测试
print("\n[Test 3] Validator...")
validator = ProtocolValidator()

# 正常校验
result, error = validator.validate_seal(seal)
print(f"  OK valid seal: {result.value}")

# 错误校验（缺少字段）
bad_seal = {"seal_id": "invalid"}
result, error = validator.validate_seal(bad_seal)
print(f"  OK invalid seal: {result.value}")

# 4. 写入队列测试
print("\n[Test 4] Write queue...")
queue = WriteQueue()
queue.enqueue(envelope)
print(f"  OK queue size: {queue.size()}")

# 处理队列
def mock_handler(e):
    print(f"    Processing: {e['cmd']}")
    return True, None

results = queue.process_all(mock_handler)
print(f"  OK processed: {len(results)} items")

print("\n" + "=" * 60)
print("All tests passed")
print("=" * 60)
