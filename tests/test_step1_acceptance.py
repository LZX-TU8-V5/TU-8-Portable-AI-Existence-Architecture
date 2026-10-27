#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 1 三验收测试
  T1: 向后兼容 — 默认参数，_estimate_subjective_gap 输出与改造前逐字节一致
  T2: 配置注入 — 自定义 TimePerceptionConfig，输出按预期变化
  T3: 接口隔离 — embodied 无 stream 必爆 RuntimeError；simple 无 stream 正常
"""
import sys
import os
import tempfile
import shutil

# 确保能 import
sys.path.insert(0, r'D:\qq366410837\.qclaw\workspace\src')
os.environ.setdefault('TU8_WORKSPACE', '')

from tu8_memory import (
    TU8MemoryEngine,
    TimePerceptionConfig,
    ISensoryStream,
)

import time as _time

# ============================================================================
# T1: 向后兼容测试
# ============================================================================
def test_t1_backward_compat():
    """默认参数实例化，_estimate_subjective_gap 输出与硬编码原值一致"""
    tmpdir = tempfile.mkdtemp(prefix="tu8_t1_")
    try:
        engine = TU8MemoryEngine(workspace_dir=tmpdir)
        now = _time.time()
        
        # Case A: system_init, 10h 离线
        # 原硬编码: sleep=min(10,8)=8, awake=2, subjective=8*0.125+2*1.0=3.0
        gap_a = engine._estimate_subjective_gap(now - 36000, now, "system_init")
        assert gap_a == 3.0, f"T1-A FAIL: expected 3.0, got {gap_a}"
        
        # Case B: system_reset, 5h 离线
        # 原硬编码: sleep=min(5,8)=5, awake=0, subjective=5*0.125+0=0.625
        gap_b = engine._estimate_subjective_gap(now - 18000, now, "system_reset")
        assert gap_b == 0.625, f"T1-B FAIL: expected 0.625, got {gap_b}"
        
        # Case C: log_scan, 3h
        # 原硬编码: 3*0.7=2.1
        gap_c = engine._estimate_subjective_gap(now - 10800, now, "log_scan")
        assert gap_c == 2.1, f"T1-C FAIL: expected 2.1, got {gap_c}"
        
        # Case D: session_end, 1h
        # 原硬编码: 1.0
        gap_d = engine._estimate_subjective_gap(now - 3600, now, "session_end")
        assert gap_d == 1.0, f"T1-D FAIL: expected 1.0, got {gap_d}"
        
        # Case E: shutdown, 0.5h
        # 原硬编码: 0.5
        gap_e = engine._estimate_subjective_gap(now - 1800, now, "shutdown")
        assert gap_e == 0.5, f"T1-E FAIL: expected 0.5, got {gap_e}"
        
        # Case F: zero gap
        gap_f = engine._estimate_subjective_gap(now, now, "system_init")
        assert gap_f == 0.0, f"T1-F FAIL: expected 0.0, got {gap_f}"
        
        print("T1 PASS: 向后兼容 — 所有输出与硬编码原值一致")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# ============================================================================
# T2: 配置注入测试
# ============================================================================
def test_t2_config_injection():
    """自定义 TimePerceptionConfig，验证输出按预期变化"""
    tmpdir = tempfile.mkdtemp(prefix="tu8_t2_")
    try:
        custom_cfg = TimePerceptionConfig(
            sleep_compression_ratio=0.2,    # 原 0.125 → 改 0.2
            max_sleep_hours_cap=6.0,        # 原 8.0 → 改 6.0
            awake_expansion_ratio=1.5,      # 原 1.0 → 改 1.5
            log_scan_compression_ratio=0.5, # 原 0.7 → 改 0.5
        )
        engine = TU8MemoryEngine(
            workspace_dir=tmpdir,
            perception_config=custom_cfg,
        )
        now = _time.time()
        
        # system_init, 10h 离线
        # sleep=min(10,6)=6, awake=4, subjective=6*0.2+4*1.5=1.2+6.0=7.2
        gap_a = engine._estimate_subjective_gap(now - 36000, now, "system_init")
        assert gap_a == 7.2, f"T2-A FAIL: expected 7.2, got {gap_a}"
        
        # log_scan, 3h
        # 3*0.5=1.5
        gap_b = engine._estimate_subjective_gap(now - 10800, now, "log_scan")
        assert gap_b == 1.5, f"T2-B FAIL: expected 1.5, got {gap_b}"
        
        # session_end 不受配置影响（直接返回客观时间）
        gap_c = engine._estimate_subjective_gap(now - 3600, now, "session_end")
        assert gap_c == 1.0, f"T2-C FAIL: expected 1.0, got {gap_c}"
        
        print("T2 PASS: 配置注入 — 输出随自定义配置正确变化")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# ============================================================================
# T3: 接口隔离测试
# ============================================================================
def test_t3_interface_isolation():
    """embodied 无 stream → RuntimeError；simple 无 stream → 正常"""
    tmpdir = tempfile.mkdtemp(prefix="tu8_t3_")
    try:
        # T3-A: embodied 无 stream → 必须抛 RuntimeError
        try:
            engine = TU8MemoryEngine(
                workspace_dir=tmpdir,
                time_perception_mode="embodied",
                sensory_stream=None,
            )
            assert False, "T3-A FAIL: embodied+None stream should have raised RuntimeError"
        except RuntimeError as e:
            assert "ISensoryStream" in str(e), f"T3-A FAIL: RuntimeError message unexpected: {e}"
            print(f"T3-A PASS: embodied 无 stream → RuntimeError('{e}')")
        
        # T3-B: simple 无 stream → 正常
        engine = TU8MemoryEngine(
            workspace_dir=tmpdir,
            time_perception_mode="simple",
            sensory_stream=None,
        )
        assert engine.time_perception_mode == "simple"
        assert engine.sensory_stream is None
        print("T3-B PASS: simple 无 stream → 正常实例化")
        
        # T3-C: invalid mode → ValueError
        try:
            engine = TU8MemoryEngine(
                workspace_dir=tmpdir,
                time_perception_mode="quantum",
            )
            assert False, "T3-C FAIL: invalid mode should have raised ValueError"
        except ValueError as e:
            print(f"T3-C PASS: invalid mode → ValueError('{e}')")
        
        # T3-D: embodied with mock stream → 正常
        class MockSensoryStream(ISensoryStream):
            def register_entropy_callback(self, callback):
                pass
            def get_average_entropy(self, start_ts, end_ts):
                return 0.5
        
        engine = TU8MemoryEngine(
            workspace_dir=tmpdir,
            time_perception_mode="embodied",
            sensory_stream=MockSensoryStream(),
        )
        assert engine.time_perception_mode == "embodied"
        assert engine.sensory_stream is not None
        print("T3-D PASS: embodied + mock stream → 正常实例化")
        
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# ============================================================================
# RUN
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Step 1 三验收测试")
    print("=" * 60)
    test_t1_backward_compat()
    test_t2_config_injection()
    test_t3_interface_isolation()
    print("=" * 60)
    print("ALL 3 TESTS PASSED ✅")
    print("=" * 60)
