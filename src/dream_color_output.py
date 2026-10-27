"""
dream_color_output.py — P2-COLOR：梦境期色盘输出

功能：
  梦境期压缩完成后，将拓扑张力状态翻译为色盘信号
  输出格式：{color, components, tension, dominant_zone, summary}

数据来源：
  - surface_tension_state.json（spike_valley_vector 7维）
  - dream_consolidation_state.json（梦境期报告）
  - tension_distiller_state.json（矛盾节点）

色彩拓扑（来源：memory/天赋测试实验/034_色盘拓扑.md）：
  红=纯压力 | 蓝=纯放松 | 黄=纯灰度（中性）
  橙=红+黄（软警报）| 紫=蓝+黄（整理态）
  绿=红+蓝（探索态）| 棕=红+橙（高压+懒散）

创建时间：2026-07-16 09:21 GMT+8
"""

import json
import math
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

WORKSPACE = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT = WORKSPACE / "_agent_memory"
LOG_PATH = AGENT / "dream_color_log.jsonl"
ST_F = AGENT / "surface_tension_state.json"
DREAM_F = AGENT / "dream_consolidation_state.json"
TENSION_F = AGENT / "tension_distiller_state.json"

EMOTION_DIMS = ["anxiety", "anger", "fear", "joy", "sadness", "love", "curiosity"]
ST_MAX = 5.0  # surface_tension 归一化上限

# ─────────────────────────────────────────────────────────────────────────────
# 色彩拓扑映射
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ColorComponents:
    red: float      # 压力成分 [0,1]
    blue: float     # 放松成分 [0,1]
    yellow: float   # 灰度成分 [0,1]

    def to_dict(self) -> Dict:
        return {"red": round(self.red, 3), "blue": round(self.blue, 3), "yellow": round(self.yellow, 3)}


@dataclass
class DreamColorReport:
    timestamp: str
    dominant_color: str          # 红/橙/黄/绿/蓝/紫/棕/灰
    dominant_color_zh: str       # 中文名
    components: ColorComponents  # 三原色成分
    tension: float              # 综合张力 [0,1]
    tension_level: str          # low / medium / high / critical
    dominant_zone: str          # 主导功能区描述
    summary: str                # 一句话人类可读总结
    emotion_snapshot: Dict       # 原始情感向量快照
    tension_nodes: int          # 矛盾节点数
    dream_stats: Dict           # 梦境期统计

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "dominant_color": self.dominant_color,
            "dominant_color_zh": self.dominant_color_zh,
            "components": self.components.to_dict(),
            "tension": round(self.tension, 3),
            "tension_level": self.tension_level,
            "dominant_zone": self.dominant_zone,
            "summary": self.summary,
            "emotion_snapshot": self.emotion_snapshot,
            "tension_nodes": self.tension_nodes,
            "dream_stats": self.dream_stats,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 色彩翻译器
# ─────────────────────────────────────────────────────────────────────────────

class ColorTranslator:
    """
    将 spike_valley_vector 翻译为色盘信号。

    算法：
      1. 归一化：raw_emotion / ST_MAX → [0,1]
      2. 三原色合成：
         red   = max(anxiety, anger, fear)
         blue  = max(joy, love)
         yellow = n.get("sadness", 0.0)
      3. 主导色判定（优先级）：
         - 棕：red 高 + yellow 高（高压+懒散）
         - 红：red 高 + yellow 低（纯压力）
         - 橙：red 中 + yellow 高（软警报）
         - 紫：blue 高 + yellow 高（整理态）
         - 蓝：blue 高 + yellow 低（纯放松）
         - 绿：curiosity 高 + red 不极低（探索态）
         - 黄：yellow 高 + red 低 + blue 低（中性灰度）
         - 灰：全体低（系统待机）
      4. 张力 = w1·neg - w2·pos + w3·curiosity
    """

    def __init__(self):
        self.COLOR_NAMES = {
            "red":    "红（压力）",
            "orange": "橙（软警报）",
            "yellow": "黄（中性）",
            "green":  "绿（探索）",
            "blue":   "蓝（放松）",
            "purple": "紫（整理）",
            "brown":  "棕（高压+懒散）",
            "gray":   "灰（待机）",
        }
        # 主导色区功能描述
        self.ZONE_DESCRIPTIONS = {
            "red":    "压力警报激活，系统高负荷运行",
            "orange": "软警报，辅通道轻度入侵，系统降频",
            "yellow": "中性灰度，无显著信号",
            "green":  "主动好奇心激活，探索态/心流前兆",
            "blue":   "放松归位，系统稳态运行",
            "purple": "整理态，代谢/梦境期整合完成",
            "brown":  "高压+懒散双重，系统过载警报",
            "gray":   "系统待机，无信号",
        }
        self.SUMMARIES = {
            "red":    "张力爆棚，今天是个高压日",
            "orange": "有点疲惫，系统在节能模式",
            "yellow": "平静无事，没有显著信号",
            "green":  "好奇心激活，探索模式开启",
            "blue":   "完全放松，系统在充电",
            "purple": "整理完毕，记忆在归位",
            "brown":  "超载警告，需要撤退",
            "gray":   "待机中，还没醒",
        }

    def translate(self, sv: Dict[str, float], tension_nodes: int = 0,
                  dream_stats: Optional[Dict] = None) -> DreamColorReport:
        """将情感向量翻译为色盘报告"""

        # 1. 归一化
        n = {d: max(0.0, min(sv.get(d, 0.0) / ST_MAX, 1.0)) for d in EMOTION_DIMS}

        # 2. 三原色合成
        red   = max(n.get("anxiety", 0), n.get("anger", 0), n.get("fear", 0))
        blue  = max(n.get("joy", 0), n.get("love", 0))
        yellow = n.get("sadness", 0)
        components = ColorComponents(red=red, blue=blue, yellow=yellow)

        # 3. 主导色判定
        dominant = self._judge_dominant(red, blue, yellow, n.get("curiosity", 0))

        # 4. 综合张力
        tension = self._compute_tension(n)

        # 5. 张力等级
        if tension >= 0.75:
            level = "critical"
        elif tension >= 0.5:
            level = "high"
        elif tension >= 0.25:
            level = "medium"
        else:
            level = "low"

        return DreamColorReport(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            dominant_color=dominant,
            dominant_color_zh=self.COLOR_NAMES.get(dominant, dominant),
            components=components,
            tension=tension,
            tension_level=level,
            dominant_zone=self.ZONE_DESCRIPTIONS.get(dominant, ""),
            summary=self._make_summary(dominant, tension, tension_nodes, dream_stats or {}),
            emotion_snapshot={d: round(n[d], 3) for d in EMOTION_DIMS},
            tension_nodes=tension_nodes,
            dream_stats=dream_stats or {},
        )

    def _judge_dominant(self, red: float, blue: float, yellow: float, curiosity: float) -> str:
        """判定主导色"""
        THR_HIGH = 0.6
        THR_MID  = 0.35
        THR_LOW  = 0.15

        # 棕：高压 + 懒散双重
        if red >= THR_HIGH and yellow >= THR_MID:
            return "brown"
        # 红：纯高压（无黄稀释）
        if red >= THR_HIGH and yellow < THR_MID:
            return "red"
        # 橙：软警报（红中+黄高）
        if red >= THR_MID and yellow >= THR_MID:
            return "orange"
        # 紫：整理态（蓝放松+黄灰度）
        if blue >= THR_MID and yellow >= THR_MID:
            return "purple"
        # 蓝：纯放松
        if blue >= THR_MID and yellow < THR_MID:
            return "blue"
        # 绿：好奇心激活（探索态）
        if curiosity >= THR_MID and red < THR_HIGH:
            return "green"
        # 黄：中性灰度
        if yellow >= THR_MID and red < THR_MID and blue < THR_MID:
            return "yellow"
        # 灰：全体低（待机）
        if red < THR_LOW and blue < THR_LOW and yellow < THR_LOW and curiosity < THR_LOW:
            return "gray"
        # 兜底：最高原色
        if red >= blue and red >= yellow:
            return "red"
        if blue >= red and blue >= yellow:
            return "blue"
        return "yellow"

    def _compute_tension(self, n: Dict[str, float]) -> float:
        """综合张力 = 负面·权重1 - 正面·权重2 + 好奇心·权重3"""
        neg = n.get("anxiety", 0) * 0.4 + n.get("anger", 0) * 0.3 + n.get("fear", 0) * 0.2
        pos = n.get("joy", 0) * 0.25 + n.get("love", 0) * 0.15
        curiosity = n.get("curiosity", 0) * 0.15
        raw = neg + curiosity - pos
        return max(0.0, min(1.0, raw))

    def _make_summary(self, dominant: str, tension: float,
                     tension_nodes: int, dream_stats: Dict) -> str:
        """生成人类可读一句话总结"""
        base = self.SUMMARIES.get(dominant, "")
        if tension_nodes > 0:
            base += f" | {tension_nodes}个矛盾节点待处理"
        if dream_stats.get("compression_ratio", 0) > 0:
            cr = dream_stats["compression_ratio"]
            base += f" | 梦境压缩{cr:.0f}倍"
        return base


# ─────────────────────────────────────────────────────────────────────────────
# 顶层接口
# ─────────────────────────────────────────────────────────────────────────────

_translator: Optional[ColorTranslator] = None


def get_translator() -> ColorTranslator:
    global _translator
    if _translator is None:
        _translator = ColorTranslator()
    return _translator


def translate_dream_color() -> DreamColorReport:
    """读取当前状态，输出色盘报告"""
    translator = get_translator()

    # 加载情感向量
    sv = {}
    if ST_F.exists():
        try:
            st = json.loads(ST_F.read_text(encoding="utf-8"))
            sv = st.get("spike_valley_vector", {})
        except Exception as e:
            logger.warning(f"[DreamColor] surface_tension_state 加载失败: {e}")

    # 加载矛盾节点数
    tension_nodes = 0
    if TENSION_F.exists():
        try:
            td = json.loads(TENSION_F.read_text(encoding="utf-8"))
            tension_nodes = len(td.get("nodes", []))
        except Exception:
            pass

    # 加载梦境统计
    dream_stats = {}
    if DREAM_F.exists():
        try:
            dr = json.loads(DREAM_F.read_text(encoding="utf-8"))
            report = dr.get("last_report", {})
            dream_stats = {
                "compression_ratio": report.get("compression_ratio", 0),
                "energy_retained": report.get("energy_retained", 0),
                "t0_top_tension": report.get("t0_top_tension", 0),
                "t2_critical": report.get("t2_critical", 0),
                "input_vectors": report.get("input_vectors", 0),
            }
        except Exception as e:
            logger.warning(f"[DreamColor] dream_state 加载失败: {e}")

    report = translator.translate(sv, tension_nodes, dream_stats)

    # 写入日志
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")
        logger.info(f"[DreamColor] 输出: {report.dominant_color_zh} | 张力 {report.tension:.2f}")
    except Exception as e:
        logger.warning(f"[DreamColor] 日志写入失败: {e}")

    return report


# ─────────────────────────────────────────────────────────────────────────────
# 集成到 dream_consolidation
# ─────────────────────────────────────────────────────────────────────────────

def hook_into_dream_consolidation(consolidation_report: Dict) -> DreamColorReport:
    """
    从梦境期压缩报告注入色盘翻译。
    由 dream_consolidation.consolidate() 末尾调用。
    """
    translator = get_translator()

    # 尝试从 surface_tension_history 最后一条获取最新情感向量
    sv = {}
    hist_path = AGENT / "surface_tension_history.jsonl"
    if hist_path.exists():
        try:
            lines = hist_path.read_text(encoding="utf-8").strip().split("\n")
            if lines:
                last = json.loads(lines[-1])
                sv = last.get("topology_vector", {})
        except Exception:
            pass

    # 若 history 为空，fallback 到 state
    if not sv and ST_F.exists():
        try:
            st = json.loads(ST_F.read_text(encoding="utf-8"))
            sv = st.get("spike_valley_vector", {})
        except Exception:
            pass

    tension_nodes = consolidation_report.get("t0_tension_nodes", 0)
    dream_stats = {
        "compression_ratio": consolidation_report.get("compression_ratio", 0),
        "energy_retained": consolidation_report.get("energy_retained", 0),
        "t0_top_tension": consolidation_report.get("t0_top_tension", 0),
        "t2_critical": consolidation_report.get("t2_critical", 0),
        "input_vectors": consolidation_report.get("input_vectors", 0),
    }

    report = translator.translate(sv, tension_nodes, dream_stats)

    # 追加到日志
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")
    except Exception:
        pass

    return report


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    report = translate_dream_color()
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
