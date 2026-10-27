"""
cron_entropy_guard.py — 注意力茧房防御的运行时触发点（P3-2d 待挂入口 #3）

触发语义：
  - 本 cron 是 entropy_guard 的**监控触发点**：周期性调用 EntropyGuard.check()
    产出 EntropyGuardReport（NORMAL/WARNING/FORCED/EMERGENCY）并落盘。
  - 守卫的数据来源是 record_activation/record_energy，由真实注意力链激活点调用。
    真实接管点 = EntropyAwareRouter.route_with_defense（src/entropy_guard.py:940），
    应在 LLM 分发路径（tu8_dispatch）中包裹 dispatch 调用以记录激活。
  - 为避免守卫在空状态下游离（无链→无检测），首次运行自动播种核心链（7链 T1-T7）
    作为监控靶标；真实激活调用会让它们保持新鲜，3天未激活则触发 EMERGENCY。

运行：由 cron_daemon.py 注册（interval 默认 3600s）串行调用，输出落 _last.json；
        本脚本另写详细状态到 _agent_memory/cron_entropy_guard_state.json。
"""
import sys
import json
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
AGENT = WS / "_agent_memory"
sys.path.insert(0, str(WS / "src"))

from entropy_guard import EntropyGuard

# 核心监控链（架构 7 链 T1-T7），首次运行播种为靶标
DEFAULT_CHAINS = ["T1", "T2", "T3", "T4", "T5", "T6", "T7"]
STATE_FILE = str(AGENT / "entropy_guard_state.json")
DETAILED_OUT = str(AGENT / "cron_entropy_guard_state.json")


def main():
    AGENT.mkdir(parents=True, exist_ok=True)
    guard = EntropyGuard(state_file=STATE_FILE)

    # 首次运行：播种核心链，避免守卫游离
    seeded = False
    if not guard.get_status().get("chains"):
        for cid in DEFAULT_CHAINS:
            guard.record_activation(cid)
        guard.save()
        seeded = True

    rep = guard.check()

    detailed = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": rep.status,
        "entropy": round(rep.entropy, 4),
        "normalized_entropy": round(rep.normalized_entropy, 4),
        "n_chains": rep.n_chains,
        "dormant_chains": rep.dormant_chains,
        "injection_triggered": rep.injection_triggered,
        "injected_chain": rep.injected_chain,
        "seeded": seeded,
        "advice": (
            "wire EntropyAwareRouter.route_with_defense into tu8_dispatch to record "
            "real activations; cron is monitoring-only trigger"
            if rep.n_chains == len(DEFAULT_CHAINS) and seeded
            else ""
        ),
    }
    with open(DETAILED_OUT, "w", encoding="utf-8") as f:
        json.dump(detailed, f, ensure_ascii=False, indent=2)

    # GBK 安全单行摘要（仅 ASCII）
    line = (
        f"[entropy_guard] status={rep.status} H={rep.normalized_entropy:.3f} "
        f"chains={rep.n_chains} dormant={len(rep.dormant_chains)} "
        f"injected={rep.injected_chain or '-'}"
    )
    print(line)

    # 非 NORMAL → 非零退出便于 cron_daemon 标记（但 daemon 仍记 ok 包装）
    if rep.status in ("WARNING", "FORCED", "EMERGENCY"):
        sys.exit(2)


if __name__ == "__main__":
    main()
