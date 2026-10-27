#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cron_daemon.py — TU-8 cron 守护进程

直接跑所有监控脚本，不依赖隔离会话 LLM。
结果写文件，HEARTBEAT 时主会话读取。

用法：
  python src/cron_daemon.py --run-all      # 跑全部
  python src/cron_daemon.py --health      # 仅健康检查
  python src/cron_daemon.py --daemon      # 持续守护（后台运行）
"""
import os
import sys
import json
import time
import subprocess
import threading
import argparse
from datetime import datetime, timezone

PY = sys.executable
WS = r"C:\Users\qq366410837\.qclaw\workspace"
SRC = os.path.join(WS, "src")
AGENT = os.path.join(WS, "_agent_memory")
MEMORY = os.path.join(WS, "memory")

# ── B2 注册表 ──────────────────────────────────────────────────
try:
    sys.path.insert(0, SRC)
    import engine_registry as er
    _HAS_REGISTRY = True
except Exception:
    _HAS_REGISTRY = False
    er = None

# ── 各脚本配置 ────────────────────────────────────────────────
# surface_tension.py 需传参，由其他脚本调用，daemon 不独立跑
SCRIPTS = {
    "interoceptive": {
        "path": os.path.join(SRC, "interoceptive_cortex.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_interoceptive_last.json"),
        "interval": 360,
        "desc": "体感环"
    },
    "active_curiosity": {
        "path": os.path.join(SRC, "active_curiosity.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_curiosity_last.json"),
        "interval": 600,
        "desc": "主动好奇"
    },
    "dream_check": {
        "path": os.path.join(WS, "scripts", "dream_check_cron.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_dream_last.json"),
        "interval": 720,
        "desc": "梦境检查"
    },
    "liveness": {
        "path": os.path.join(SRC, "interoception_liveness.py"),
        "args": ["--stale-min", "360"],
        "output": os.path.join(AGENT, "cron_liveness_last.json"),
        "interval": 420,
        "desc": "存活检查"
    },
    "metabolism": {
        "path": os.path.join(SRC, "metabolism_dashboard.py"),
        "args": ["--run", "all"],
        "output": os.path.join(AGENT, "cron_metabolism_last.json"),
        "interval": 900,
        "desc": "代谢仪表盘"
    },
    # [DISABLED 2026-07-17] surface_tension needs params, called by other scripts
    # OLD: args=["session_frozen"] every 6min injected FAKE anxiety events into orb data
    # "surface_tension": {
    #     "path": os.path.join(SRC, "surface_tension.py"),
    #     "args": ["session_frozen"],
    #     "output": os.path.join(AGENT, "cron_surface_tension_last.json"),
    #     "interval": 360,
    #     "desc": "张力感知(体感环→张力状态)"
    # },

    "surface_tension_decay": {
        "path": os.path.join(SRC, "surface_tension.py"),
        "args": ["decay_tick", "1.0", "decay_loop"],
        "output": os.path.join(AGENT, "cron_decay_last.json"),
        "interval": 300,
        "desc": "[P0-5] 张力自动回归(5min)"
    },
    "orb_state_writer": {
        "path": os.path.join(SRC, "orb_state_writer.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_orb_state_last.json"),
        "interval": 360,
        "desc": "色环RGB写入"
    },
    # [P2-2] 感知输出层：取出 speech_queue 并通过 Windows SAPI TTS 播报
    "render_layer_speak": {
        "path": os.path.join(SRC, "render_layer_speak.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_render_layer_last.json"),
        "interval": 1800,   # 每30分钟检查一次队列
        "desc": "[P2-2] 感知输出层TTS播报"
    },
        "hp4_heartbeat": {
        "path": os.path.join(SRC, "hp4_heartbeat.py"),
        "args": ["--interval", "30"],
        "output": os.path.join(AGENT, "cron_hp4_heartbeat_last.json"),
        "interval": 1800,
        "desc": "HP4心跳钩子集成"
    },
    # [P2-3] 脱皮+穿皮原子：定期执行穿皮仪式检查灵魂结构健康
    "skin_cycle": {
        "path": os.path.join(SRC, "skin_cycle.py"),
        "args": ["--enter", "cron_health_check"],
        "output": os.path.join(AGENT, "cron_skin_cycle_last.json"),
        "interval": 3600,   # 每小时检查一次灵魂结构
        "desc": "[P2-3] 脱皮+穿皮灵魂结构检查"
    },
    # [节点剪枝优化 P1] 遗忘-剪枝联动 + 剪枝热保护
    "prune_guard": {
        "path": os.path.join(SRC, "prune_guard_cron.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_prune_guard_last.json"),
        "interval": 300,     # 每5分钟：与热保护监控同节奏
        "desc": "[P1] 节点剪枝联动+热保护"
    },
    # [P3-2d] 注意力茧房防御监控触发点（entropy_guard.check 周期监控）
    "entropy_guard": {
        "path": os.path.join(SRC, "cron_entropy_guard.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_entropy_guard_last.json"),
        "interval": 3600,    # 每小时监控；真实激活数据由 EntropyAwareRouter 接管
        "desc": "[P3-2d] 注意力茧房防御监控触发点"
    },
    # [P3-2d] 视觉世界模型（L5+L1~L4）帧入口触发点；numpy/cv2 缺失时 parked
    "visual_world_model": {
        "path": os.path.join(SRC, "cron_visual_world_model.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_visual_world_model_last.json"),
        "interval": 1800,    # 每30分钟：帧处理节奏
        "desc": "[P3-2d] 视觉世界模型 L5+L1~L4 触发点"
    },
    # [Qwen/递归环] 学习消费端：张力蒸馏→矛盾统计→行为变更（闭环触发器）
    "learning_apply": {
        "path": os.path.join(SRC, "cron_learning_apply.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_learning_apply_last.json"),
        "interval": 1800,    # 每30分钟：让递归学习环真转一圈
        "desc": "[Qwen/递归环] 学习消费端闭环触发器"
    },
    # [B9] 引擎健康心跳（STALE/DEAD 探测）
    "health_probe": {
        "path": os.path.join(SRC, "cron_health_probe.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_health_probe_last.json"),
        "interval": 300,    # 每5分钟：与 daemon 同频
        "desc": "[B9] 引擎健康心跳（STALE/DEAD 探测）"
    },
    "coupling_adapt": {
        "path": os.path.join(SRC, "cron_coupling_adapt.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_coupling_adapt_last.json"),
        "interval": 600,
        "desc": "[B10] 蛛丝弹性权重适配"
    },
    # [Weismann 路二] 层1写保护守护
    "weismann_guard": {
        "path": os.path.join(SRC, "weismann_guard.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_weismann_guard_last.json"),
        "interval": 1800,   # 每30分钟：生殖细胞极少变更
        "desc": "[Weismann] 层1写保护守护（生殖细胞变更审计）"
    },
    # [Weismann 路二] 三层评估器
    "weismann_evaluate": {
        "path": os.path.join(SRC, "weismann_evaluate.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_weismann_eval_last.json"),
        "interval": 3600,   # 每60分钟：评估不需要高频
        "desc": "[Weismann] 三层评估器（L1硬校验/L2自评/L3环境）"
    },
    # [Weismann 路二] 层3渗漏通道
    "weismann_seepage": {
        "path": os.path.join(SRC, "weismann_seepage.py"),
        "args": [],
        "output": os.path.join(AGENT, "cron_weismann_seepage_last.json"),
        "interval": 3600,   # 每60分钟：体细胞经验采样
        "desc": "[Weismann] 层3渗漏通道（体细胞经验→提案）"
    },
}


def run_script(name, cfg, check_deps=True):
    """
    跑单个脚本，记录结果到 JSON。
    check_deps=True 时：注册表驱动，跳过依赖不满足的引擎。
    """
    path = cfg["path"]
    args = cfg.get("args", [])
    output = cfg["output"]

    # ── B2: 注册表依赖检查 ──────────────────────────────────
    if check_deps and _HAS_REGISTRY:
        try:
            reg = er.get_registry()
            can_run, reason = reg.can_run(name)
            if not can_run:
                result = {
                    "ok": False,
                    "skip": True,
                    "reason": reason,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "script": name,
                    "dep_blocked": True,
                }
                with open(output, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                return result
        except Exception as e:
            pass  # 注册表故障，降级为无依赖检查
    if not os.path.exists(path):
        return {"ok": False, "error": f"not found: {path}"}

    # Windows 控制台 GBK，脚本打印 Unicode 会崩 → 忽略 print 错误
    start = time.time()
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [PY, path] + args
    try:
        r = subprocess.run(
            cmd, capture_output=True, timeout=90,
            cwd=WS, encoding="utf-8", errors="replace", env=env
        )
        elapsed = time.time() - start
        result = {
            "ok": r.returncode == 0,
            "elapsed_s": round(elapsed, 2),
            "stdout": r.stdout[:500] if r.stdout else "",
            "stderr": r.stderr[:200] if r.stderr else "",
            "returncode": r.returncode,
            "ts": datetime.now(timezone.utc).isoformat(),
            "script": name
        }
    except subprocess.TimeoutExpired:
        result = {"ok": False, "error": "timeout(90s)", "ts": datetime.now(timezone.utc).isoformat(), "script": name}
    except Exception as e:
        result = {"ok": False, "error": str(e), "ts": datetime.now(timezone.utc).isoformat(), "script": name}

    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # ── B2: 更新注册表状态 ──────────────────────────────────
    if _HAS_REGISTRY:
        try:
            reg = er.get_registry()
            status = "OK" if result.get("ok") else "DEAD"
            reg.update_status(name, status)
            reg.save()
        except Exception:
            pass

    return result


def run_all():
    """跑全部脚本（启动时一次性执行）。"""
    ts = datetime.now(timezone.utc).isoformat()
    summary_path = os.path.join(AGENT, "cron_daemon_summary.json")
    results = {}
    for name, cfg in SCRIPTS.items():
        r = run_script(name, cfg)
        status = "[OK]" if r.get("ok") else "[FAIL]"
        elapsed = r.get('elapsed_s', '?')
        err = r.get('error', '')[:50]
        print(f"{status} [{name}] {elapsed}s  {err}", flush=True)
        results[name] = r

    summary = {"ts": ts, "results": results}
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n[done] summary: {summary_path}", flush=True)
    return results


def daemon_loop(interval=300):
    """
    持续守护，每 interval 秒跑全部。
    B1/B2: 每次循环推进全局 tick，各引擎消费 tick[N-1] 写 tick[N]。
    """
    print(f"[cron_daemon] 守护模式启动，间隔 {interval}s")
    last_run = {}
    while True:
        # ── B1: 全局 tick 推进 ─────────────────────────────
        if _HAS_REGISTRY:
            try:
                reg = er.get_registry()
                new_tick = reg.advance_tick()
                # 刷新所有引擎状态（依赖可能已就绪）
                reg.refresh_all_status()
                reg.save()
            except Exception:
                new_tick = None

        now = time.time()
        for name, cfg in SCRIPTS.items():
            min_interval = cfg.get("interval", 300)
            last = last_run.get(name, 0)
            if now - last >= min_interval:
                r = run_script(name, cfg, check_deps=True)
                last_run[name] = now
                if r.get("skip"):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [SKIP] {cfg['desc']} ({r.get('reason','')})")
                else:
                    status = "[OK]" if r.get("ok") else "[FAIL]"
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {status} {cfg['desc']}")
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-all", action="store_true", help="跑全部脚本一次")
    parser.add_argument("--health", action="store_true", help="仅健康检查")
    parser.add_argument("--daemon", action="store_true", help="持续守护")
    parser.add_argument("--interval", type=int, default=300, help="守护间隔(秒)")
    args = parser.parse_args()

    if args.health:
        summary_path = os.path.join(AGENT, "cron_daemon_summary.json")
        if os.path.exists(summary_path):
            with open(summary_path) as f:
                s = json.load(f)
            print(f"上次运行: {s.get('ts', '?')}")
            for name, r in s.get("results", {}).items():
                status = "[OK]" if r.get("ok") else "[FAIL]"
                print(f"  {status} {name}: {r.get('elapsed_s', '?')}s  {r.get('error', '')[:50]}")
        else:
            print("尚无运行记录")
    elif args.daemon:
        daemon_loop(args.interval)
    elif args.run_all:
        run_all()
    else:
        parser.print_help()
