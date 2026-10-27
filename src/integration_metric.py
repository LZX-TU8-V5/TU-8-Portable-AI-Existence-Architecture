"""
IntegrationMetric - 整合度标尺
测量梦境补丁/占位符与主拓扑的整合程度，给出整合完成信号。
"""

import json
import os
from pathlib import Path
from typing import Optional

STATE_FILE = Path(__file__).parent.parent / "_agent_memory" / "integration_metric_state.json"


class IntegrationMetric:
    """
    整合度标尺：测量补丁整合程度，判定整合状态。
    """

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or STATE_FILE
        self._ensure_state_dir()
        self._state: dict = self._load_state()

    # ------------------------------------------------------------------ internal

    def _ensure_state_dir(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_state(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ public API

    def measure(self, patch_id: str) -> dict:
        """
        测量补丁整合度。

        内部逻辑：
        - 从持久化状态读取 patch_id 的检测结果
        - 若未检测过，返回 "isolated" 状态（无数据 = 孤立）

        三联检测：
        1. background_ratio : 补丁区域被主拓扑覆盖的比例
        2. placeholder_ratio: 补丁被稳定占位符替代的比例
        3. residual_ratio   : 补丁独立残差占总面积的比例

        整合度 = background_ratio * 0.5 + placeholder_ratio * 0.3 + (1 - residual_ratio) * 0.2

        参数:
            patch_id: 补丁唯一标识

        返回:
            dict，包含 patch_id, integration_score, background_ratio,
            placeholder_ratio, residual_ratio, status, recommendation
        """
        patch_data = self._state.get(patch_id, {})

        if not patch_data:
            # 未检测：保守判定为孤立
            return {
                "patch_id": patch_id,
                "integration_score": 0.0,
                "background_ratio": 0.0,
                "placeholder_ratio": 0.0,
                "residual_ratio": 1.0,
                "status": "isolated",
                "recommendation": f"补丁 [{patch_id}] 尚未检测，建议先执行拓扑检测。",
            }

        bg = float(patch_data.get("background_ratio", 0.0))
        ph = float(patch_data.get("placeholder_ratio", 0.0))
        res = float(patch_data.get("residual_ratio", 1.0))

        # 整合度公式：背景覆盖为主(0.6)，微弱残差为辅(0.3)，占位符微调(0.1)
        # 分数范围: [0,1]
        score = bg * 0.6 + (1.0 - res) * 0.3 + ph * 0.1
        score = round(min(max(score, 0.0), 1.0), 4)

        status = self._score_to_status(score)
        recommendation = self._recommend(status, patch_id)

        result = {
            "patch_id": patch_id,
            "integration_score": score,
            "background_ratio": round(bg, 4),
            "placeholder_ratio": round(ph, 4),
            "residual_ratio": round(res, 4),
            "status": status,
            "recommendation": recommendation,
        }

        # 持久化
        self._state[patch_id] = result
        self._save_state()

        return result

    def is_integrated(self, patch_id: str, threshold: float = 0.8) -> bool:
        """
        判断补丁是否已完全整合。

        参数:
            patch_id  : 补丁唯一标识
            threshold : 整合阈值，默认 0.8

        返回:
            bool，integration_score >= threshold 时返回 True
        """
        metric = self.measure(patch_id)
        return metric["integration_score"] >= threshold

    def get_all_metrics(self) -> list:
        """
        返回所有已检测补丁的整合度列表。

        返回:
            list[dict]，每个元素同 measure() 返回值
        """
        results = []
        for patch_id in self._state:
            results.append(self.measure(patch_id))
        return results

    # ------------------------------------------------------------------ private helpers

    @staticmethod
    def _score_to_status(score: float) -> str:
        if score >= 0.8:
            return "integrated"
        elif score >= 0.5:
            return "partial"
        elif score >= 0.2:
            return "weak"
        else:
            return "isolated"

    @staticmethod
    def _recommend(status: str, patch_id: str) -> str:
        rec_map = {
            "integrated": f"补丁 [{patch_id}] 已完成整合，可并入主拓扑稳定运行。",
            "partial": f"补丁 [{patch_id}] 部分整合，建议持续观察并补充覆盖检测。",
            "weak": f"补丁 [{patch_id}] 整合度弱，需增强主拓扑覆盖或替换占位符。",
            "isolated": f"补丁 [{patch_id}] 孤立存在，建议重新评估纳入拓扑的可行性。",
        }
        return rec_map.get(status, "")


# -------------------------------------------------------------------------- __main__


if __name__ == "__main__":
    import tempfile

    # 使用临时文件隔离测试
    tmp_file = Path(tempfile.gettempdir()) / "test_integration_metric.json"
    metric = IntegrationMetric(state_file=tmp_file)

    print("=" * 60)
    print("  IntegrationMetric 验证测试")
    print("=" * 60)

    # 模拟注入各状态补丁数据
    test_cases = {
        # patch_id -> {background_ratio, placeholder_ratio, residual_ratio}
        "patch_fully_covered": {
            "background_ratio": 0.90,
            "placeholder_ratio": 0.05,
            "residual_ratio": 0.05,
        },
        "patch_partial": {
            "background_ratio": 0.55,
            "placeholder_ratio": 0.20,
            "residual_ratio": 0.30,
        },
        "patch_weak": {
            "background_ratio": 0.25,
            "placeholder_ratio": 0.10,
            "residual_ratio": 0.65,
        },
        "patch_isolated": {
            "background_ratio": 0.05,
            "placeholder_ratio": 0.00,
            "residual_ratio": 0.95,
        },
    }

    # 预填充状态（模拟已检测）
    for pid, data in test_cases.items():
        metric._state[pid] = data
    metric._save_state()

    # 重新实例化，确保从持久化读取
    metric = IntegrationMetric(state_file=tmp_file)

    # 1. 验证各状态判定
    print("\n[1] 各状态判定测试\n")
    status_labels = {
        "integrated": "完全整合",
        "partial": "部分整合",
        "weak": "整合度弱",
        "isolated": "孤立",
    }

    for pid in test_cases:
        m = metric.measure(pid)
        print(f"  {pid}")
        print(f"    score={m['integration_score']:.4f}  status={m['status']}  "
              f"bg={m['background_ratio']:.2f}  ph={m['placeholder_ratio']:.2f}  "
              f"res={m['residual_ratio']:.2f}")
        print(f"    → {m['recommendation']}")
        print()

    # 2. 验证 is_integrated 阈值判断
    print("[2] is_integrated 阈值判断测试（threshold=0.8）\n")
    expected = {
        "patch_fully_covered": True,
        "patch_partial": False,
        "patch_weak": False,
        "patch_isolated": False,
    }

    all_pass = True
    for pid, exp in expected.items():
        result = metric.is_integrated(pid, threshold=0.8)
        tag = "PASS" if result == exp else "FAIL"
        all_pass = all_pass and (result == exp)
        print(f"  [{tag}] {pid}: is_integrated={result}  expected={exp}")

    # 3. 未检测补丁返回 isolated
    print("\n[3] 未检测补丁默认状态测试\n")
    m_new = metric.measure("patch_brand_new")
    print(f"  {m_new['status']}  score={m_new['integration_score']}  "
          f"recommendation: {m_new['recommendation']}")

    print("\n" + "=" * 60)
    if all_pass:
        print("  All tests passed.")
    else:
        print("  Some tests FAILED.")
    print("=" * 60)

    # 清理
    tmp_file.unlink(missing_ok=True)
