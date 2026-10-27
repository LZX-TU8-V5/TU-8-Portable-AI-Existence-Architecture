#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dream_check_cron.py — TU-8 梦境期 Cron 任务入口
触发：每4小时 / 每天3am / 每周日5am
动作：调用 ConsciousnessCycle._enter_deep_sleep() 执行深睡三操作
"""
import sys, os, json, logging
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path.home() / ".qclaw" / "workspace"
sys.path.insert(0, str(WORKSPACE / "src"))

# 抑制正常 INFO 日志，只留警告
import pathlib  # 新增：补丁 pathlib 导入
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# 直觉引擎初始化（深睡期后触发模式匹配）
INTUITION_LOG = WORKSPACE / "memory" / "intuition_dream_log.jsonl"

def _run_intuition_match():
    """深睡期后，用今日关键事件触发直觉匹配"""
    try:
        sys.path.insert(0, str(WORKSPACE / "src"))
        from intuition_engine import IntuitionEngine
        engine = IntuitionEngine()
        
        # 读取今日日记（作为情境输入）
        today = datetime.now().strftime('%Y-%m-%d')
        diary = WORKSPACE / "memory" / f"{today}.md"
        if not diary.exists():
            return
        
        situation = diary.read_text(encoding='utf-8')[:500]  # 前500字符作为情境
        result = engine.match(situation, threshold=0.15)
        
        if result:
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "dream_check",
                "pattern_id": result.pattern_id,
                "confidence": result.confidence,
                "latency_ms": result.latency_ms,
            }
            with open(INTUITION_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            print(f"  [intuition] 匹配到模式 {result.pattern_id}，置信度={result.confidence:.2f}")
        else:
            print("  [intuition] 无匹配")
    except Exception as e:
        print(f"  [intuition] WARNING: {e}")

def main():
    from consciousness_cycle import ConsciousnessCycle

    # === T3 调度链：登记梦境期任务 ===
    dream_id = None
    try:
        sys.path.insert(0, str(WORKSPACE / "src"))
        from t3_middleware import ensure_dream_task, record_dream_result
        scheduler_t3 = True
    except Exception:
        scheduler_t3 = False
        print("  [T3] WARNING: scheduler not available")

    # 最小化实例（仅 config 必填）
    cc = ConsciousnessCycle(config=None, memory_engine=None, reflection_module=None)

    # === L1 Dream WAL：梦境期事务开始（防硬杀跨文件不一致 / 身首异处）===
    _dream_ok = True
    def _dtx():
        try:
            sys.path.insert(0, str(WORKSPACE / "src"))
            import dream_txn as _m
            return _m
        except Exception:
            return None
    try:
        _m = _dtx()
        if _m:
            _today = datetime.now().strftime('%Y-%m-%d')
            _targets = [
                str(WORKSPACE / "MEMORY.md"),
                str(WORKSPACE / "memory" / f"{_today}.md"),
                str(WORKSPACE / "memory" / "_dream_state.json"),
                str(WORKSPACE / "memory" / "body_regulation.json"),
                str(WORKSPACE / "memory" / "intuition_bias.json"),
            ]
            _m.begin(["deep_sleep", "metabolic", "intuition", "learning"], _targets)
    except Exception as e:
        print(f"  [dream_txn] WARNING begin: {e}")

    print(f"[dream_check] Phase before: {cc.phase.value}")
    report = cc._enter_deep_sleep()
    print(f"[dream_check] Phase after: {cc.phase.value}")

    # 提取 dream_id 用于 T3 任务登记
    dream_id = report.get("deep_sleep_number")
    if scheduler_t3 and dream_id:
        ensure_dream_task(dream_id)
        record_dream_result(dream_id, 'deep_sleep', True, {
            'ops': len(report.get("operations", [])),
            'errors': len(report.get("errors", [])),
        })

    # 摘要输出
    ops = report.get("operations", [])
    for op in ops:
        name = op.get("name", "?")
        items = {k: v for k, v in op.items() if k != "name"}
        print(f"  {name}: {items}")

    errors = report.get("errors", [])
    if errors:
        print(f"  ERRORS: {errors}")
    else:
        print("  [OK] No errors")

    # 写入状态文件（供下次查询）
    state_file = WORKSPACE / "memory" / ".dream_check_last_run.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": report.get("timestamp"),
            "deep_sleep_number": report.get("deep_sleep_number"),
            "operations": ops,
            "errors": errors,
        }, f, ensure_ascii=False, indent=2)

    print(f"[dream_check] Done. Report saved to {state_file}")

    # === 代谢循环（深睡期后自动运行）：统一驱动所有代谢子系统 ===
    # 调用 src/metabolism_dashboard.py 的完整代谢循环
    # 包含：置信度衰减 + GC→学习 + 代谢管道（蒸馏+去重+GC+归档）
    try:
        sys.path.insert(0, str(WORKSPACE / "src"))
        from metabolism_dashboard import run_full_metabolism_cycle
        result = run_full_metabolism_cycle(dry_run=False)
        ok_count = result.get("ok_count", 0)
        total = result.get("total_count", 0)
        print(f"  [metabolism] {ok_count}/{total} 子系统 OK | health={result.get('health_score')}%")
        # 细节日志
        for key, val in result.get("results", {}).items():
            icon = "✅" if val.get("ok") else "❌"
            err = f" | ERROR: {val.get('error', '')[:50]}" if not val.get("ok") else ""
            print(f"    {icon} {key}{err}")
        if scheduler_t3 and dream_id:
            record_dream_result(dream_id, 'metabolic', ok_count == total, {"ok": ok_count, "total": total})
    except Exception as e:
        _dream_ok = False
        print(f"  [metabolism] WARNING: {e}")
        if scheduler_t3 and dream_id:
            record_dream_result(dream_id, 'metabolic', False, {'error': str(e)[:100]})

    # === 直觉引擎（深睡期后模式匹配）===
    try:
        _run_intuition_match()
        if scheduler_t3 and dream_id:
            record_dream_result(dream_id, 'intuition', True, {})
    except Exception as e:
        _dream_ok = False
        print(f"  [intuition] WARNING: {e}")
        if scheduler_t3 and dream_id:
            record_dream_result(dream_id, 'intuition', False, {'error': str(e)[:100]})

    # === 第5链：自主学习（代谢之后，梦境期后半段）===
    try:
        sys.path.insert(0, str(WORKSPACE / "src"))
        from learning_engine import LearningEngine
        engine = LearningEngine()
        learn_result = engine.run()
        status = learn_result.get("status", "?")
        if status == "complete":
            decisions = learn_result.get("decisions", {})
            applied = learn_result.get("applied", 0)
            print(f"  [learning] Cycle #{learn_result['cycle_id']}: {decisions}, applied={applied}")
        elif status == "skipped":
            print(f"  [learning] Cycle #{learn_result['cycle_id']}: skipped ({learn_result.get('reason', '?')})")
        else:
            print(f"  [learning] Cycle #{learn_result['cycle_id']}: {status}")
        
        # 输出详细报告（日志文件）
        report = learn_result.get("report", "")
        if report:
            report_path = WORKSPACE / "memory" / f"_learning_cycle_{learn_result['cycle_id']}.log"
            report_path.write_text(report, encoding="utf-8")
        if scheduler_t3 and dream_id:
            record_dream_result(dream_id, 'learning', learn_result.get('status') == 'complete', {
                'cycle_id': learn_result.get('cycle_id'),
                'applied': learn_result.get('applied', 0),
            })
    except ImportError as e:
        _dream_ok = False
        print(f"  [learning] 模块未就绪: {e}")
        if scheduler_t3 and dream_id:
            record_dream_result(dream_id, 'learning', False, {'error': str(e)[:100]})
    except Exception as e:
        _dream_ok = False
        print(f"  [learning] WARNING: {e}")
        if scheduler_t3 and dream_id:
            record_dream_result(dream_id, 'learning', False, {'error': str(e)[:100]})

    # === L1 Dream WAL：事务提交（仅当全阶段成功；否则保留日志待 boot 重基线）===
    try:
        _m = _dtx()
        if _m:
            if _dream_ok:
                _m.commit()
                print("  [dream_txn] committed")
            else:
                print("  [dream_txn] 有阶段失败：保留未完成日志，boot 将触发重基线（unknown 保活）")
    except Exception as e:
        print(f"  [dream_txn] WARNING commit: {e}")

    # === P1-D0 R3: batch_confidence 梦境期 flush ===
    # 梦境期结束后强制flush所有脏节点到磁盘（延迟I/O统一结算）
    try:
        sys.path.insert(0, str(WORKSPACE / "src"))
        import batch_confidence_updater as bcu
        updater = bcu.BatchConfidenceUpdater(
            flush_threshold=9999,   # 不自动flush
            flush_interval=99999,  # 靠强制flush
        )
        updater.flush_now()
        summary = updater.cost_summary()
        print(f"  [batch_confidence] flush: {summary.get('nodes_in_cache', 0)} cached, "
              f"{summary.get('flush_count', 0)} total flushes")
    except ImportError:
        print("  [batch_confidence] not available (import error)")
    except Exception as e:
        print(f"  [batch_confidence] WARNING: {e}")

if __name__ == "__main__":
    main()
