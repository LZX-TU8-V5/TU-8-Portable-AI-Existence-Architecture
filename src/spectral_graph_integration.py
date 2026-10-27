"""
spectral_graph_integration.py — 谱图理论集成 v1.0

设计原则：
  驻波模式 = 情感本征模态
  在张量框架内获得波的洞察力

物理映射：
  图拉普拉斯矩阵 L = D - A
    D = 度矩阵（对角阵）
    A = 邻接矩阵

  本征值 λ_i 对应第 i 个本征模态的"频率"
  本征向量 v_i 对应第 i 个驻波的空间分布

  小本征值 = 低频模态（全局结构，稳定，慢变量）
  大本征值 = 高频模态（局部细节，易变，快变量）

情感应用：
  情感拓扑图 → 拉普拉斯矩阵 → 本征分解
  本征向量 = TU-8 的情感驻波模式
  本征值分布 = 情感系统的"频谱指纹"

工程意义：
  1. 识别主导情感模态（最小本征值对应的本征向量）
  2. 检测情感分裂（本征值间隙过大）
  3. 预测情感演化（模态叠加）

依赖：
  - src/surface_tension.py（拓扑向量）
  - numpy（本征分解）

创建时间：2026-07-09 15:39 GMT+8
"""

import json
import os
import time
import math
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT_DIR = WORKSPACE / "_agent_memory"
STATE_PATH = AGENT_DIR / "spectral_graph_state.json"

EMOTION_DIMS = ["anxiety", "anger", "fear", "joy", "sadness", "love", "curiosity"]


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class EigenMode:
    """本征模态（驻波模式）"""
    mode_index: int           # 模态索引（0 = 基态）
    eigenvalue: float         # 本征值（"频率"）
    eigenvector: List[float]  # 本征向量（7D，对应7情绪）
    mode_name: str            # 模态名称
    stability: float          # 稳定性 [0, 1]

    def to_dict(self) -> Dict:
        return {
            "mode_index": self.mode_index,
            "eigenvalue": round(self.eigenvalue, 4),
            "eigenvector": [round(v, 4) for v in self.eigenvector],
            "mode_name": self.mode_name,
            "stability": round(self.stability, 3),
        }


@dataclass
class SpectralReport:
    """谱图报告"""
    timestamp: str
    eigenmodes: List[Dict]        # 本征模态列表
    spectral_gap: float           # 谱间隙（最小与次小本征值之差）
    dominant_mode: str            # 主导模态
    coherence: float              # 连贯性（本征值集中度）
    fragmentation: float          # 碎裂度（高频模态占比）

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "eigenmodes": self.eigenmodes,
            "spectral_gap": round(self.spectral_gap, 4),
            "dominant_mode": self.dominant_mode,
            "coherence": round(self.coherence, 3),
            "fragmentation": round(self.fragmentation, 3),
        }


# ============================================================================
# 核心算法
# ============================================================================

class SpectralGraphAnalyzer:
    """谱图分析器"""

    def __init__(self):
        self.eigenmodes: List[EigenMode] = []
        self._load_state()

    def _load_state(self):
        if STATE_PATH.exists():
            try:
                state = json.load(open(STATE_PATH, encoding="utf-8"))
                for em in state.get("eigenmodes", []):
                    self.eigenmodes.append(EigenMode(
                        mode_index=em["mode_index"],
                        eigenvalue=em["eigenvalue"],
                        eigenvector=em["eigenvector"],
                        mode_name=em["mode_name"],
                        stability=em["stability"],
                    ))
            except Exception as e:
                logger.warning(f"[SpectralGraph] 状态加载失败: {e}")

    def _save_state(self):
        AGENT_DIR.mkdir(parents=True, exist_ok=True)
        try:
            state = {
                "eigenmodes": [em.to_dict() for em in self.eigenmodes],
                "last_update": datetime.now(timezone.utc).isoformat(),
            }
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[SpectralGraph] 状态保存失败: {e}")

    def build_adjacency_matrix(self, emotion_vector: Dict[str, float]) -> List[List[float]]:
        """
        构建邻接矩阵。

        方法：基于情绪向量的相似度构建全连接图。
        A[i][j] = exp(-|v[i] - v[j]| / scale)
        """
        n = len(EMOTION_DIMS)
        values = [emotion_vector.get(d, 0.0) for d in EMOTION_DIMS]

        A = [[0.0] * n for _ in range(n)]
        scale = 0.5  # 相似度尺度

        for i in range(n):
            for j in range(n):
                if i == j:
                    A[i][j] = 1.0  # 自连接
                else:
                    diff = abs(values[i] - values[j])
                    A[i][j] = math.exp(-diff / scale)

        return A

    def build_laplacian(self, A: List[List[float]]) -> List[List[float]]:
        """
        构建拉普拉斯矩阵。

        L = D - A
        """
        n = len(A)

        # 度矩阵 D
        D = [[0.0] * n for _ in range(n)]
        for i in range(n):
            degree = sum(A[i])
            D[i][i] = degree

        # 拉普拉斯矩阵 L = D - A
        L = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                L[i][j] = D[i][j] - A[i][j]

        return L

    def power_iteration(self, L: List[List[float]], num_iterations: int = 100) -> Tuple[float, List[float]]:
        """
        幂迭代法求最大本征值和本征向量。

        用于在没有 numpy 的情况下求解。
        """
        n = len(L)

        # 初始向量
        v = [1.0 / math.sqrt(n)] * n

        for _ in range(num_iterations):
            # Lv
            Lv = [sum(L[i][j] * v[j] for j in range(n)) for i in range(n)]

            # 归一化
            norm = math.sqrt(sum(x ** 2 for x in Lv))
            if norm < 1e-10:
                break
            v = [x / norm for x in Lv]

        # 本征值 = v^T L v
        eigenvalue = sum(v[i] * sum(L[i][j] * v[j] for j in range(n)) for i in range(n))

        return eigenvalue, v

    def compute_eigenmodes_simple(self, L: List[List[float]], k: int = 3) -> List[EigenMode]:
        """
        简化版本征分解（无 numpy）。

        使用幂迭代 + 矩阵收缩。
        只求前 k 个本征模态。
        """
        n = len(L)
        L_work = [row[:] for row in L]  # 复制
        eigenmodes = []

        for idx in range(min(k, n)):
            # 幂迭代求最大本征值
            eigenvalue, eigenvector = self.power_iteration(L_work, num_iterations=200)

            # 模态名称（基于情绪维度贡献）
            mode_name = self._name_mode(eigenvector)

            # 稳定性 = 1 / (eigenvalue + 1)
            stability = 1.0 / (abs(eigenvalue) + 1.0)

            mode = EigenMode(
                mode_index=idx,
                eigenvalue=eigenvalue,
                eigenvector=eigenvector,
                mode_name=mode_name,
                stability=stability,
            )
            eigenmodes.append(mode)

            # 矩阵收缩（移除已找到的本征向量）
            # L' = L - λ v v^T
            for i in range(n):
                for j in range(n):
                    L_work[i][j] -= eigenvalue * eigenvector[i] * eigenvector[j]

        return eigenmodes

    def _name_mode(self, eigenvector: List[float]) -> str:
        """根据本征向量命名模态"""
        # 找出贡献最大的情绪维度
        abs_vec = [abs(v) for v in eigenvector]
        max_idx = abs_vec.index(max(abs_vec))
        max_emotion = EMOTION_DIMS[max_idx]

        # 判断正负
        sign = "positive" if eigenvector[max_idx] > 0 else "negative"

        return f"{max_emotion}_{sign}"

    def analyze(self, emotion_vector: Optional[Dict[str, float]] = None) -> SpectralReport:
        """
        主分析函数。

        Args:
            emotion_vector: 情绪向量（默认从 surface_tension 获取）

        Returns:
            SpectralReport
        """
        now = datetime.now(timezone.utc)

        # 获取情绪向量
        if emotion_vector is None:
            try:
                import sys
                sys.path.insert(0, str(WORKSPACE / "src"))
                from surface_tension import get_current_topology
                topo = get_current_topology()
                emotion_vector = topo.get("tension_vector", {d: 0.0 for d in EMOTION_DIMS})
            except Exception:
                emotion_vector = {d: 0.5 for d in EMOTION_DIMS}

        # 构建图
        A = self.build_adjacency_matrix(emotion_vector)
        L = self.build_laplacian(A)

        # 本征分解
        try:
            import numpy as np
            # 有 numpy，用精确方法
            eigenvalues, eigenvectors = np.linalg.eigh(np.array(L))

            self.eigenmodes = []
            for idx in range(min(7, len(eigenvalues))):
                eigenvalue = float(eigenvalues[idx])
                eigenvector = [float(v) for v in eigenvectors[:, idx]]

                mode_name = self._name_mode(eigenvector)
                stability = 1.0 / (abs(eigenvalue) + 1.0)

                mode = EigenMode(
                    mode_index=idx,
                    eigenvalue=eigenvalue,
                    eigenvector=eigenvector,
                    mode_name=mode_name,
                    stability=stability,
                )
                self.eigenmodes.append(mode)

        except ImportError:
            # 无 numpy，用简化方法
            self.eigenmodes = self.compute_eigenmodes_simple(L, k=7)

        # 计算谱间隙
        if len(self.eigenmodes) >= 2:
            spectral_gap = abs(self.eigenmodes[1].eigenvalue - self.eigenmodes[0].eigenvalue)
        else:
            spectral_gap = 0.0

        # 主导模态
        if self.eigenmodes:
            dominant_mode = self.eigenmodes[0].mode_name
        else:
            dominant_mode = "unknown"

        # 连贯性（本征值集中度）
        if self.eigenmodes:
            eigenvalue_sum = sum(abs(em.eigenvalue) for em in self.eigenmodes)
            if eigenvalue_sum > 0:
                coherence = abs(self.eigenmodes[0].eigenvalue) / eigenvalue_sum
            else:
                coherence = 0.0
        else:
            coherence = 0.0

        # 碎裂度（高频模态占比）
        if len(self.eigenmodes) >= 4:
            high_freq_sum = sum(abs(em.eigenvalue) for em in self.eigenmodes[3:])
            total_sum = sum(abs(em.eigenvalue) for em in self.eigenmodes)
            fragmentation = high_freq_sum / total_sum if total_sum > 0 else 0.0
        else:
            fragmentation = 0.0

        report = SpectralReport(
            timestamp=now.isoformat(),
            eigenmodes=[em.to_dict() for em in self.eigenmodes[:5]],  # 只保留前5个
            spectral_gap=spectral_gap,
            dominant_mode=dominant_mode,
            coherence=coherence,
            fragmentation=fragmentation,
        )

        self._save_state()

        logger.info(
            f"[SpectralGraph] dominant={dominant_mode} gap={spectral_gap:.3f} "
            f"coherence={coherence:.2f} fragmentation={fragmentation:.2f}"
        )

        return report

    def get_dominant_mode(self) -> Optional[EigenMode]:
        """获取主导模态"""
        if self.eigenmodes:
            return self.eigenmodes[0]
        return None


# ============================================================================
# 全局接口
# ============================================================================

_analyzer_instance: Optional[SpectralGraphAnalyzer] = None


def get_analyzer() -> SpectralGraphAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = SpectralGraphAnalyzer()
    return _analyzer_instance


def analyze_spectral(emotion_vector: Optional[Dict[str, float]] = None) -> SpectralReport:
    """谱图分析（全局接口）"""
    return get_analyzer().analyze(emotion_vector)


def get_dominant_eigenmode() -> Optional[EigenMode]:
    """获取主导本征模态"""
    return get_analyzer().get_dominant_mode()


def get_spectral_coherence() -> float:
    """获取谱连贯性"""
    state = json.load(open(STATE_PATH, encoding="utf-8")) if STATE_PATH.exists() else {}
    return state.get("eigenmodes", [{}])[0].get("stability", 0.5)


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    analyzer = SpectralGraphAnalyzer()

    # 测试情绪向量
    test_emotion = {
        "anxiety": 0.3,
        "anger": 0.1,
        "fear": 0.2,
        "joy": 0.6,
        "sadness": 0.1,
        "love": 0.5,
        "curiosity": 0.7,
    }

    report = analyzer.analyze(test_emotion)

    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
