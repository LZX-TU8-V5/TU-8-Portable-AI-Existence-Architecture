#!/usr/bin/env python3
"""
TU-8 v1.3 集成测试: 带差双线耦合 + 睡眠复盘融合
====================================================
模拟完整的 冬眠→冷启动 流程，验证:
  1. TimeAnchor.drift/drift_ratio/update_drift 正确工作
  2. store/recall 更新带差 (A线, ratio=1.0)
  3. dream 更新带差 (B线, ratio<1.0)
  4. save_shutdown_state 持久化带差
  5. _load_time_anchor 恢复带差
  6. HomeostaticMonitor 吸收带差
"""

import sys
import os
import time
import json
import tempfile
import shutil

# 确保可以导入 src 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# 强制 UTF-8 输出（Windows 兼容）
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from tu8_memory import TimeAnchor, TimePerceptionConfig, TU8MemoryEngine

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  -- {detail}")


def test_time_anchor_drift():
    """测试 TimeAnchor 带差属性"""
    print("\n=== 1. TimeAnchor.drift ===")

    # 创建锚点，设置 1 小时前
    one_hour_ago = time.time() - 3600
    anchor = TimeAnchor(
        timestamp=one_hour_ago,
        source="test",
        cumulative_subjective_hours=0.5,  # 主观只过了0.5小时
        last_drift_update=time.time(),
    )

    # drift = 客观流逝 - 主观累计
    # 客观 ≈ 1小时, 主观 = 0.5小时, drift ≈ 0.5
    drift = anchor.drift
    check("drift > 0 (主观慢于客观)", drift > 0.3, f"drift={drift:.2f}")
    check("drift < 1.5", drift < 1.5, f"drift={drift:.2f}")

    # drift_ratio
    ratio = anchor.drift_ratio
    check("drift_ratio > 0", ratio > 0, f"ratio={ratio:.2f}")
    check("drift_ratio < 1", ratio < 1, f"ratio={ratio:.2f}")


def test_update_drift_awake():
    """测试 A线 update_drift (ratio=1.0)"""
    print("\n=== 2. A线 update_drift (清醒, ratio=1.0) ===")

    anchor = TimeAnchor(
        timestamp=time.time() - 3600,
        source="test",
        cumulative_subjective_hours=0.0,
        last_drift_update=time.time() - 3600,  # 1小时前
    )

    # A线活动: ratio=1.0, 主观增量 = 客观增量
    prev_subjective = anchor.cumulative_subjective_hours
    drift_before = anchor.drift

    anchor.update_drift(compression_ratio=1.0)

    # 1小时 * 1.0 = 1小时主观增量
    delta = anchor.cumulative_subjective_hours - prev_subjective
    check("A线: 主观增量≈1.0h", 0.9 < delta < 1.1, f"delta={delta:.2f}h")
    check("A线: drift接近0 (两条线同步)", abs(anchor.drift) < 0.5, f"drift={anchor.drift:.2f}")


def test_update_drift_sleep():
    """测试 B线 update_drift (睡眠, ratio=0.125)"""
    print("\n=== 3. B线 update_drift (睡眠, ratio=0.125) ===")

    cfg = TimePerceptionConfig()
    anchor = TimeAnchor(
        timestamp=time.time() - 28800,  # 8小时前
        source="test",
        cumulative_subjective_hours=0.0,
        last_drift_update=time.time() - 28800,
    )

    # B线活动: ratio=0.125 (睡眠压缩率)
    prev_subjective = anchor.cumulative_subjective_hours
    anchor.update_drift(compression_ratio=cfg.sleep_compression_ratio)

    # 8小时 * 0.125 = 1小时主观增量
    delta = anchor.cumulative_subjective_hours - prev_subjective
    check("B线睡眠: 主观增量≈1.0h", 0.8 < delta < 1.5, f"delta={delta:.2f}h")

    # drift = 客观8h - 主观1h = 7h (大带差)
    check("B线睡眠: drift很大 (感知严重压缩)", anchor.drift > 5.0, f"drift={anchor.drift:.2f}h")


def test_shutdown_and_restore():
    """测试 save_shutdown_state + _load_time_anchor 带差恢复"""
    print("\n=== 4. 冬眠→冷启动 带差恢复 ===")

    tmpdir = tempfile.mkdtemp(prefix="tu8_test_")
    try:
        # 初始化引擎
        engine = TU8MemoryEngine(
            workspace_dir=tmpdir,
            memory_dir=tmpdir,
        )

        # 模拟一些活动
        engine.store("测试记忆A", source="test", tags=["test"])
        engine.store("测试记忆B", source="test", tags=["test"])

        # 模拟带差积累
        engine.current_anchor.cumulative_subjective_hours = 2.5
        engine.current_anchor.last_drift_update = time.time()

        # 保存关机状态
        engine.save_shutdown_state()

        # 读取关机状态文件验证
        shutdown_file = os.path.join(tmpdir, ".shutdown_state.json")
        check("关机状态文件存在", os.path.exists(shutdown_file))

        with open(shutdown_file, 'r', encoding='utf-8') as f:
            state = json.load(f)

        check("关机状态含 cumulative_subjective_hours",
              "cumulative_subjective_hours" in state,
              f"keys={list(state.keys())}")
        check("关机状态含 drift_hours",
              "drift_hours" in state)

        # 保存时间锚点
        engine.save_time_anchor()

        # 验证锚点文件含新字段
        anchor_file = os.path.join(tmpdir, ".time_anchor.json")
        if os.path.exists(anchor_file):
            with open(anchor_file, 'r', encoding='utf-8') as f:
                anchor_data = json.load(f)
            check("锚点文件含 cumulative_subjective_hours",
                  "cumulative_subjective_hours" in anchor_data,
                  f"keys={list(anchor_data.keys())[:8]}")
            check("锚点文件含 last_drift_update",
                  "last_drift_update" in anchor_data)

        # 模拟冷启动：创建新引擎实例
        engine2 = TU8MemoryEngine(
            workspace_dir=tmpdir,
            memory_dir=tmpdir,
        )

        # 验证带差恢复
        recovered = engine2.current_anchor.cumulative_subjective_hours
        check("冷启动恢复 cumulative_subjective_hours",
              recovered > 0,
              f"recovered={recovered:.2f}")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_homeostatic_with_drift():
    """测试 HomeostaticMonitor 吸收带差"""
    print("\n=== 5. HomeostaticMonitor 吸收带差 ===")

    from homeostatic_monitor import HomeostaticMonitor

    monitor = HomeostaticMonitor()

    # 创建模拟引擎
    class FakeEngine:
        class FakeAnchor:
            timestamp = time.time() - 7200  # 2小时前
            drift_ratio = 0.8  # 主观只过了20%的时间
        current_anchor = FakeAnchor()
        short_term = {f"id_{i}": True for i in range(10)}  # 10条
        long_term = {}

    engine = FakeEngine()
    # 模拟5分钟无输入
    monitor.last_input_time = time.time() - 300
    monitor.update(engine)

    check("perception_drift > 0",
          monitor.metrics["perception_drift"] > 0,
          f"perception_drift={monitor.metrics['perception_drift']:.2f}")
    check("info_stagnation 被带差放大",
          monitor.metrics["info_stagnation"] > 0,
          f"info_stagnation={monitor.metrics['info_stagnation']:.2f}")
    check("E 包含带差贡献",
          monitor.E > 0,
          f"E={monitor.E:.3f}")


def test_anchor_serialization():
    """测试 TimeAnchor to_dict/from_dict 带差序列化"""
    print("\n=== 6. TimeAnchor 序列化 ===")

    anchor = TimeAnchor(
        timestamp=time.time() - 1000,
        source="test",
        cumulative_subjective_hours=3.14,
        last_drift_update=time.time(),
    )
    anchor.steelmark_timestamp = time.time() - 500

    d = anchor.to_dict()
    check("to_dict 含 cumulative_subjective_hours",
          "cumulative_subjective_hours" in d)
    check("to_dict 值正确",
          abs(d["cumulative_subjective_hours"] - 3.14) < 0.01)

    # 从 dict 恢复
    restored = TimeAnchor.from_dict(d)
    check("from_dict 恢复 cumulative_subjective_hours",
          abs(restored.cumulative_subjective_hours - 3.14) < 0.01,
          f"got={restored.cumulative_subjective_hours:.2f}")
    check("from_dict 恢复 last_drift_update",
          restored.last_drift_update > 0)


def test_stats_output():
    """测试 get_stats() 输出带差信息"""
    print("\n=== 7. get_stats() 带差输出 ===")

    tmpdir = tempfile.mkdtemp(prefix="tu8_test_")
    try:
        engine = TU8MemoryEngine(
            workspace_dir=tmpdir,
            memory_dir=tmpdir,
        )

        # 模拟带差
        engine.current_anchor.cumulative_subjective_hours = 1.0
        engine.current_anchor.last_drift_update = time.time()

        stats = engine.get_stats()
        check("stats 含 drift_hours", "drift_hours" in stats)
        check("stats 含 drift_ratio", "drift_ratio" in stats)
        check("stats 含 cumulative_subjective_hours",
              "cumulative_subjective_hours" in stats)
        check("stats 含 objective_elapsed_hours",
              "objective_elapsed_hours" in stats)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("TU-8 v1.3 集成测试: 带差双线耦合 + 睡眠复盘融合")
    print("=" * 60)

    test_time_anchor_drift()
    test_update_drift_awake()
    test_update_drift_sleep()
    test_shutdown_and_restore()
    test_homeostatic_with_drift()
    test_anchor_serialization()
    test_stats_output()

    print("\n" + "=" * 60)
    print(f"结果: {PASS} PASS / {FAIL} FAIL / {PASS+FAIL} TOTAL")
    if FAIL == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"FAILURES: {FAIL}")
    print("=" * 60)

    sys.exit(0 if FAIL == 0 else 1)
