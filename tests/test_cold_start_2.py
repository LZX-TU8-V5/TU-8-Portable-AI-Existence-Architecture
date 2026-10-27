# -*- coding: utf-8 -*-
# encoding: utf-8
"""
test_cold_start.py — TU-8 P0 cold start engine unit tests
Focus: DNA fingerprint F(A) computation & verification

Run: python src/test_cold_start.py
"""
# 创作者: 李奥(金木蟾) | TU-8 v5

import sys
import os
import json
import hashlib
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.cold_start_engine import ColdStartEngine


def test_dna_fingerprint_deterministic():
    """F(A) deterministic: same input -> same output"""
    print("\n=== Test 1: F(A) Deterministic ===")
    
    l0_hash = hashlib.sha256("test_l0_content".encode()).hexdigest()
    ts = "2026-05-31T10:00:00+00:00"
    creator_id = "v5::CREATOR"
    
    engine = ColdStartEngine()
    
    fp1 = engine._compute_dna_fingerprint(l0_hash, ts, creator_id)
    fp2 = engine._compute_dna_fingerprint(l0_hash, ts, creator_id)
    
    assert fp1 == fp2, "F(A) should be deterministic"
    assert len(fp1) == 64, f"F(A) should be full SHA256 (64 chars), got {len(fp1)}"
    print(f"  [PASS] F(A) deterministic: {fp1[:16]}...")
    return True


def test_dna_fingerprint_uniqueness():
    """F(A) uniqueness: different timestamp -> different fingerprint"""
    print("\n=== Test 2: F(A) Uniqueness (1ms diff) ===")
    
    l0_hash = hashlib.sha256("test_l0_content".encode()).hexdigest()
    creator_id = "v5::CREATOR"
    
    engine = ColdStartEngine()
    
    ts1 = "2026-05-31T10:00:00.000000+00:00"
    ts2 = "2026-05-31T10:00:00.001000+00:00"
    
    fp1 = engine._compute_dna_fingerprint(l0_hash, ts1, creator_id)
    fp2 = engine._compute_dna_fingerprint(l0_hash, ts2, creator_id)
    
    assert fp1 != fp2, "different timestamps -> different F(A)"
    print(f"  [PASS] F(A) time-sensitivity:")
    print(f"     T0+0ms  -> {fp1[:16]}...")
    print(f"     T0+1ms  -> {fp2[:16]}...")
    return True


def test_dna_fingerprint_l0_tamper():
    """F(A) detects L0 tampering"""
    print("\n=== Test 3: F(A) L0 Tamper Detection ===")
    
    engine = ColdStartEngine()
    
    l0_hash_original = hashlib.sha256("original_l0".encode()).hexdigest()
    l0_hash_tampered = hashlib.sha256("tampered_l0".encode()).hexdigest()
    ts = "2026-05-31T10:00:00+00:00"
    creator_id = "v5::CREATOR"
    
    fp_original = engine._compute_dna_fingerprint(l0_hash_original, ts, creator_id)
    fp_tampered = engine._compute_dna_fingerprint(l0_hash_tampered, ts, creator_id)
    
    assert fp_original != fp_tampered, "L0 tampered -> F(A) different"
    print(f"  [PASS] L0 tamper detection:")
    print(f"     original L0 F(A) -> {fp_original[:16]}...")
    print(f"     tampered L0 F(A) -> {fp_tampered[:16]}...")
    return True


def test_genesis_block_creation():
    """Genesis block creation flow"""
    print("\n=== Test 4: Genesis Block Creation ===")
    
    tmp_dir = tempfile.mkdtemp(prefix="tu8_test_")
    try:
        engine = ColdStartEngine(workspace_dir=tmp_dir)
        
        result = engine.create_genesis_block(
            cold_start_type="FIRST",
            dormancy_hours=0,
            dormancy_type="night_sleep"
        )
        
        assert result["status"] == "PASS", f"Creation should pass, got: {result}"
        assert "genesis_block_path" in result
        assert "creator_id" in result
        
        block_path = Path(tmp_dir) / "memory" / "time_chain" / "genesis_block.json"
        assert block_path.exists(), "genesis_block file should exist"
        
        with open(block_path, "r", encoding="utf-8") as f:
            block = json.load(f)
        
        required = ["creator_id", "creator_timestamp", "l0_hash", 
                     "dna_fingerprint", "activation_code_hash", "host_fingerprint",
                     "session_seed", "cold_start_type"]
        for field in required:
            assert field in block, f"Missing field: {field}"
        
        assert len(block["dna_fingerprint"]) == 64, "F(A) should be full SHA256"
        assert "dna_formula" in block, "Should include formula doc"
        
        lock_path = Path(tmp_dir) / "memory" / "time_chain" / "p0_complete.lock"
        assert lock_path.exists(), "Causal lock file should exist"
        
        print(f"  [PASS] Genesis Block created:")
        print(f"     creator_id: {block['creator_id']}")
        print(f"     F(A): {block['dna_fingerprint'][:16]}...")
        print(f"     L0 hash: {block['l0_hash'][:16]}...")
        print(f"     host FP: {block['host_fingerprint']}")
        print(f"     causal lock: YES")
        return True
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_dna_fingerprint_verify():
    """DNA fingerprint verification (P1 scenario)"""
    print("\n=== Test 5: F(A) Verification (P1 scenario) ===")
    
    tmp_dir = tempfile.mkdtemp(prefix="tu8_test_")
    try:
        engine = ColdStartEngine(workspace_dir=tmp_dir)
        
        result = engine.create_genesis_block(cold_start_type="FIRST")
        assert result["status"] == "PASS"
        
        block_path = Path(tmp_dir) / "memory" / "time_chain" / "genesis_block.json"
        with open(block_path, "r", encoding="utf-8") as f:
            block = json.load(f)
        stored_fp = block["dna_fingerprint"]
        
        engine2 = ColdStartEngine(workspace_dir=tmp_dir)
        is_valid = engine2.verify_dna_fingerprint(stored_fp)
        assert is_valid, "correct F(A) should verify"
        print(f"  [PASS] correct F(A) verification: PASS")
        
        is_valid_false = engine2.verify_dna_fingerprint("0" * 64)
        assert not is_valid_false, "wrong F(A) should be rejected"
        print(f"  [PASS] wrong F(A) verification: REJECTED")
        
        return True
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_environment_detection():
    """Environment detection (no side effects)"""
    print("\n=== Test 6: Environment Detection ===")
    
    engine = ColdStartEngine()
    env = engine.detect_environment()
    
    assert "host_identity" in env
    assert "workspace_integrity" in env
    assert "runtime" in env
    assert "environment_status" in env
    
    print(f"  [PASS] Environment detection:")
    print(f"     host: {env['host_identity']['hostname']} ({env['host_identity']['trust_level']})")
    print(f"     workspace: {env['workspace_integrity']['status']}")
    print(f"     runtime: {env['runtime']['status']}")
    print(f"     overall: {env['environment_status']}")
    return True


def test_session_gap_detection():
    """Session gap detection"""
    print("\n=== Test 7: Session Gap Detection ===")
    
    tmp_dir = tempfile.mkdtemp(prefix="tu8_test_")
    try:
        engine = ColdStartEngine(workspace_dir=tmp_dir)
        
        gap = engine.detect_session_gap()
        assert gap["label"] == "FIRST_BOOT"
        assert gap["cold_start_depth"] == "FULL"
        print(f"  [PASS] First boot: {gap['label']} -> {gap['cold_start_depth']}")
        
        return True
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_full_cold_start_auto():
    """Full auto cold start flow"""
    print("\n=== Test 8: Auto Cold Start (Full Flow) ===")
    
    tmp_dir = tempfile.mkdtemp(prefix="tu8_test_")
    try:
        engine = ColdStartEngine(workspace_dir=tmp_dir)
        report = engine.run_auto_cold_start()
        
        assert "result" in report
        assert "phases" in report
        
        print(f"  [PASS] Auto cold start:")
        print(f"     env: {report['phases'].get('environment', {}).get('environment_status', 'N/A')}")
        print(f"     gap: {report['phases'].get('session_gap', {}).get('label', 'N/A')}")
        print(f"     result: {report.get('result', 'N/A')}")
        return True
        
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# =============================================================================
# Runner
# =============================================================================

def main():
    tests = [
        ("F(A) Deterministic", test_dna_fingerprint_deterministic),
        ("F(A) Uniqueness", test_dna_fingerprint_uniqueness),
        ("F(A) L0 Tamper Detection", test_dna_fingerprint_l0_tamper),
        ("Genesis Block Creation", test_genesis_block_creation),
        ("F(A) Verification", test_dna_fingerprint_verify),
        ("Environment Detection", test_environment_detection),
        ("Session Gap Detection", test_session_gap_detection),
        ("Auto Cold Start Flow", test_full_cold_start_auto),
    ]
    
    print("=" * 60)
    print("TU-8 P0 Cold Start Engine -- Unit Tests")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed / {failed} failed / {len(tests)} total")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
