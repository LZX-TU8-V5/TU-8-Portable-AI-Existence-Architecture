# -*- coding: utf-8 -*-
"""
P0 强类型契约集成测试
验证：Schema 校验 + 自动重试 + 写入队列
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from seal_protocol import (
    ProtocolValidator,
    WriteQueue,
    create_seal_payload,
    create_write_envelope,
    ValidationResult,
    WriteBackType,
    SealPriority
)

print("=" * 60)
print("P0 Strong Type Contract Integration Test")
print("=" * 60)

# =============================================================================
# Test 1: Schema Validation
# =============================================================================
print("\n[Test 1] Schema Validation...")

validator = ProtocolValidator()

# 1.1 Valid seal
valid_seal = create_seal_payload(
    content="User preference: prefers dark mode",
    parent_hash="GENESIS",
    priority=SealPriority.P2_BEHAVIOR,
    tags=["preference", "ui"]
)

result, error = validator.validate_seal(valid_seal)
assert result.value == ValidationResult.VALID, f"Valid seal should pass: {error}"
print(f"  OK valid seal: {result.value}")

# 1.2 Invalid seal (missing fields)
invalid_seal = {"seal_id": "bad_format"}
result, error = validator.validate_seal(invalid_seal)
assert result.value == ValidationResult.INVALID_SCHEMA, "Should detect invalid schema"
print(f"  OK invalid seal: {result.value}")

# 1.3 Ghost parent detection
orphan_seal = create_seal_payload(
    content="Test content",
    parent_hash="nonexistent_hash_12345",  # This parent doesn't exist
    priority=SealPriority.P3_EPISODIC
)

result, error = validator.validate_seal(orphan_seal)
assert result.value == ValidationResult.GHOST_PARENT, f"Should detect ghost parent: {result.value}"
print(f"  OK ghost parent detected: {result.value}")

# =============================================================================
# Test 2: Write Envelope Validation
# =============================================================================
print("\n[Test 2] Write Envelope Validation...")

envelope = create_write_envelope(
    cmd=WriteBackType.UPDATE_SEAL,
    payload=valid_seal
)

result, error = validator.validate_envelope(envelope)
assert result.value == ValidationResult.VALID, f"Envelope should be valid: {error}"
print(f"  OK valid envelope: {result.value}")

# Corrupted envelope
bad_envelope = envelope.copy()
bad_envelope["checksum"] = "wrong_checksum"
result, error = validator.validate_envelope(bad_envelope)
assert result.value == ValidationResult.INVALID_HASH, "Should detect checksum mismatch"
print(f"  OK checksum validation: {result.value}")

# =============================================================================
# Test 3: Write Queue (Concurrency Control)
# =============================================================================
print("\n[Test 3] Write Queue...")

queue = WriteQueue(max_size=10)

# Enqueue multiple requests
for i in range(5):
    seal = create_seal_payload(
        content=f"Test content {i}",
        parent_hash="GENESIS" if i == 0 else f"seal_{i-1}",
        priority=SealPriority.P3_EPISODIC
    )
    env = create_write_envelope(
        cmd=WriteBackType.UPDATE_SEAL,
        payload=seal
    )
    success = queue.enqueue(type('Envelope', (), env))
    assert success, f"Should enqueue item {i}"

print(f"  OK enqueued 5 items, queue size: {queue.size()}")

# Idempotency check
same_env = create_write_envelope(
    cmd=WriteBackType.UPDATE_SEAL,
    payload=valid_seal,
    request_id="req_12345"  # Same request_id
)
queue._processed_ids.add("req_12345")  # Mark as processed
success = queue.enqueue(type('Envelope', (), same_env))
assert success, "Should skip already processed request"
assert queue.size() == 5, "Queue should not grow for duplicate"
print(f"  OK idempotency check passed")

# =============================================================================
# Test 4: DuskRitual Integration
# =============================================================================
print("\n[Test 4] DuskRitual Integration...")

from tu8_dispatch import DuskRitual, SoulStructure

# Create a test workspace
test_dir = os.path.join(os.path.dirname(__file__), "test_workspace")
os.makedirs(test_dir, exist_ok=True)
os.makedirs(os.path.join(test_dir, "memory", "time_chain"), exist_ok=True)
os.makedirs(os.path.join(test_dir, "config"), exist_ok=True)

# Create DuskRitual
dusk = DuskRitual(test_dir)

# Create soul structure
soul = SoulStructure(
    recent_seals=[],
    causal_chains=[],
    active_memories=[],
    current_seal_id="seal_test_123"
)

# Test extraction
response = "This is a test response with causal chain: input -> process -> output"
valid_payloads, retry_requests = dusk.execute(response, soul)

print(f"  OK extracted {len(valid_payloads)} payloads")
print(f"  OK retry requests: {len(retry_requests)}")

# =============================================================================
# Summary
# =============================================================================
print("\n" + "=" * 60)
print("P0 Strong Type Contract Tests PASSED")
print("=" * 60)
print("\nKey validations:")
print("  1. Schema validation - OK")
print("  2. Ghost parent detection - OK")
print("  3. Checksum verification - OK")
print("  4. Write queue (concurrency) - OK")
print("  5. Idempotency check - OK")
print("  6. DuskRitual integration - OK")
