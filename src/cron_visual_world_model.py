"""
cron_visual_world_model.py — 视觉世界模型（L5 + L1~L4）运行时触发点（P3-2d 待挂入口 #1/#2）

触发语义：
  - 本 cron 是视觉管线（dual_mode_switcher[L5] + world_model_l1l4[L1~L4]）的**帧入口触发点**。
  - 真实链路：帧源 → DualModeSliceSwitcher.switch(frame) → L5FrameReport
                     → SingularityUnifier → UnifiedSceneReport
                     → WorldModelL1L4.run(L5Input) → WorldModelState
  - L5 阶段依赖 numpy + cv2（图像数组）；本环境 numpy/cv2 缺失 → 自动 parked。
  - parked 状态明确记录待装依赖（numpy + opencv-python）与帧源配置（VIDEO_SOURCE）。
    装好依赖后本 cron 自动激活全链路，无需改代码。

帧源配置（环境变量 VIDEO_SOURCE，可选）：
  - "0" / 整数       → 摄像头索引（cv2.VideoCapture(0)）
  - 路径/目录         → 图片或视频文件
  - 默认 "0"（webcam）

运行：由 cron_daemon.py 注册（interval 默认 1800s）串行调用，输出落 _last.json；
        本脚本另写详细状态到 _agent_memory/cron_visual_world_model_state.json。
"""
import sys
import os
import json
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
AGENT = WS / "_agent_memory"
sys.path.insert(0, str(WS / "src"))

DETAILED_OUT = str(AGENT / "cron_visual_world_model_state.json")
FRAME_CAP = int(os.environ.get("VISUAL_FRAME_CAP", "10"))
VIDEO_SOURCE = os.environ.get("VIDEO_SOURCE", "0")


def _write_state(state: dict):
    AGENT.mkdir(parents=True, exist_ok=True)
    state["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(DETAILED_OUT, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _parked(reason: str):
    state = {
        "status": "parked",
        "stage": "L5",
        "reason": reason,
        "advice": "install numpy + opencv-python, set VIDEO_SOURCE (camera idx / file)",
        "video_source": VIDEO_SOURCE,
    }
    _write_state(state)
    print(f"[visual_wm] PARKED: {reason}")
    # parked 是合法的等待态，非零退出会让 cron_daemon 标失败；保持 0
    sys.exit(0)


def main():
    # L5 阶段硬依赖 numpy（图像数组）+ cv2（帧源）
    try:
        import numpy as np  # noqa: F401
        import cv2  # noqa: F401
        from dual_mode_switcher import DualModeSliceSwitcher
        from singularity_unifier import SingularityUnifier
        from world_model_l1l4 import WorldModelL1L4, WorldModelL5Input
    except ImportError as e:
        _parked(f"missing dependency: {e} (L5 stage requires numpy+cv2)")

    # ── 以下仅在 numpy/cv2 可用时执行 ──
    switcher = DualModeSliceSwitcher()
    unifier = SingularityUnifier()
    l1l4 = WorldModelL1L4()

    # 读帧
    try:
        src = int(VIDEO_SOURCE)
        cap = cv2.VideoCapture(src)
    except ValueError:
        cap = cv2.VideoCapture(VIDEO_SOURCE)

    frames = []
    t0 = time.time()
    while len(frames) < FRAME_CAP and (time.time() - t0) < 20.0:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()

    if not frames:
        state = {"status": "no_frames", "video_source": VIDEO_SOURCE,
                 "advice": "check VIDEO_SOURCE (camera connected? valid file?)"}
        _write_state(state)
        print(f"[visual_wm] no frames from {VIDEO_SOURCE}")
        return

    # L5：逐帧双模态切换
    l5_reports = [switcher.switch(f) for f in frames]
    # 奇点统一（基于末帧 + 轨迹）
    scene_report = unifier.unify(frames[-1], object_trajectory=None)
    motion_report = None  # decoupler 已并入 switcher；如需细化可在此接 l5_motion_decoupler

    inp = WorldModelL5Input(scene_report=scene_report, motion_report=motion_report)
    wm_state = l1l4.run(inp)

    state = {
        "status": "ok",
        "stage": "L5+L1~L4",
        "n_frames": len(frames),
        "scene_objects": len(getattr(wm_state, "scene", None) and wm_state.scene.primitives or []),
        "video_source": VIDEO_SOURCE,
    }
    _write_state(state)
    print(f"[visual_wm] OK frames={len(frames)} objects={state['scene_objects']}")


if __name__ == "__main__":
    main()
