"""
chain_coupling_analyzer.py — 5链耦合诊断

检验学5条的中间件完整性，检测缺失的适配层。
"""

import json, os, sys, time
from pathlib import Path

WORKSPACE = Path(os.environ.get("TU8_WORKSPACE", os.path.expanduser("~/.qclaw/workspace")))

# 定义5链
CHAINS = {
    "T1-时间钢印": {
        "modules": ["seal_manager", "seal_protocol", "steel_seal_verifier", 
                     "genesis_cycle", "cognitive_time_engine"],
        "data_out": "决策历史、钢印记录、时间锚点",
        "data_in": "学习产物的底层铁律",
    },
    "T2-记忆": {
        "modules": ["tu8_memory", "memory_adapter", "tu8_agent"],
        "data_out": "内容积累、检索结果、存储反馈",
        "data_in": "学习产物的记忆笔记",
    },
    "T3-调度": {
        "modules": ["task_scheduler", "tu8_dispatch", "tu8_planner", "tu8_toolchain"],
        "data_out": "任务耗时、错误分布、执行反馈",
        "data_in": "规则修正（TOOLS.md）影响调度行为",
    },
    "T4-代谢": {
        "modules": ["memory_gc", "memory_dedup", "metabolic_pipeline", "profile_update_loop"],
        "data_out": "归档通知、丢弃记录、衰减趋势",
        "data_in": "学习链的产物生命周期同步",
    },
    "T5-学习": {
        "modules": ["learning_*", "intuition_engine", "anomaly_detector",
                     "cognitive_pain_monitor", "profile_update_loop"],
        "data_out": "模式发现、规则修正、偏好更新",
        "data_in": "各链数据作为传感器输入",
    },
}


class ChainCouplingChecker:
    """检查5链间的数据流中间件完整性"""

    MIDDLEWARE_TABLE = {
        # (from, to): (中间件文件, 是否已实现)
        ("T1", "T5"): ("seal_to_learning_adapter", False),
        ("T2", "T5"): ("memory_to_learning_adapter", False),
        ("T3", "T5"): ("dispatch_to_learning_adapter", False),
        ("T5", "T4"): ("learning_to_gc_adapter", False),
        ("T4", "T5"): ("gc_to_learning_adapter", False),
        ("T1", "T4"): ("seal_to_gc_adapter", False),
        ("T3", "T4"): ("dispatch_to_gc_adapter", False),
        ("T2", "T4"): ("memory_to_gc_adapter", False),
        ("T5", "T1"): ("learning_to_seal_adapter", False),
        ("T5", "T2"): ("learning_to_memory_adapter", False),
        ("T5", "T3"): ("learning_to_dispatch_adapter", False),
    }

    def __init__(self):
        self.results = []
        self._check_existing_adapters()

    def _check_existing_adapters(self):
        """扫描已存在的中间件（仅检查文件是否存在）"""
        src_dir = WORKSPACE / "src"
        if not src_dir.exists():
            return
        for key in list(self.MIDDLEWARE_TABLE.keys()):
            middleware_file, _ = self.MIDDLEWARE_TABLE[key]
            file_path = src_dir / f"{middleware_file}.py"
            if file_path.exists():
                self.MIDDLEWARE_TABLE[key] = (middleware_file, True)

    def check_coupling(self) -> dict:
        """检查所有链间中间件的就绪状态"""
        report = {"missing": [], "existing": [], "metadata_missing": []}

        for (from_chain, to_chain), (mw_file, exists) in self.MIDDLEWARE_TABLE.items():
            from_name = CHAINS[next(k for k in CHAINS if k.startswith(from_chain))]["modules"]
            to_name = CHAINS[next(k for k in CHAINS if k.startswith(to_chain))]["modules"]

            status = "✅ 已实现" if exists else "❌ 缺失"
            entry = {
                "from": f"T{from_chain}",
                "to": f"T{to_chain}",
                "middleware": mw_file,
                "exists": exists,
                "status": status,
            }
            if exists:
                report["existing"].append(entry)
            else:
                report["missing"].append(entry)

        # 额外检查：已有管道（dream_check_cron）是否挂接了所有链
        dream_check = WORKSPACE / "scripts" / "dream_check_cron.py"
        if dream_check.exists():
            content = dream_check.read_text(encoding="utf-8")
            hooks = {
                "代谢链": "metabolic_pipeline" in content,
                "学习链": "learning_engine" in content,
                "直觉引擎": "intuition_engine" in content,
            }
            report["pipeline_hooks"] = hooks

        return report

    def print_report(self, report: dict):
        print("=" * 60)
        print("5链耦合诊断报告")
        print("=" * 60)

        print(f"\n✅ 已实现的中间件 ({len(report['existing'])}):")
        for e in report["existing"]:
            print(f"  {e['from']}→{e['to']}: {e['middleware']}")

        print(f"\n❌ 缺失的中间件 ({len(report['missing'])}):")
        for e in report["missing"]:
            print(f"  {e['from']}→{e['to']}: {e['middleware']}")

        if "pipeline_hooks" in report:
            print(f"\n📦 dream_check_cron 管道挂接:")
            for name, hook in report["pipeline_hooks"].items():
                print(f"  {'✅' if hook else '❌'} {name}")

        print(f"\n{'='*60}")
        print(f"缺失率: {len(report['missing'])}/{len(report['missing'])+len(report['existing'])}")
        print(f"{'='*60}")

    def save_to_doc(self, report: dict):
        doc = "# 5链耦合中间件分析\n\n"
        doc += f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M')}\n\n"
        doc += "## 现状\n\n"
        doc += f"- 已实现: {len(report['existing'])} 个中间件\n"
        doc += f"- 缺失: {len(report['missing'])} 个中间件\n\n"

        doc += "## 已实现的中间件\n\n"
        doc += "| 从 | 到 | 中间件 |\n|------|------|------|\n"
        for e in report["existing"]:
            doc += f"| {e['from']} | {e['to']} | `{e['middleware']}` |\n"

        doc += "\n## 缺失的中间件\n\n"
        doc += "| 从 | 到 | 中间件 | 说明 | 优先级 |\n|------|------|------|------|------|\n"
        
        priorities = {
            ("T1", "T5"): "P1",
            ("T2", "T5"): "P2",
            ("T3", "T5"): "P2",
            ("T5", "T4"): "P0",
            ("T4", "T5"): "P1",
            ("T1", "T4"): "P2",
            ("T3", "T4"): "P2",
            ("T2", "T4"): "P2",
            ("T5", "T1"): "P2",
            ("T5", "T2"): "P2",
            ("T5", "T3"): "P2",
        }
        descriptions = {
            ("T1", "T5"): "钢印记录→学习链传感器：学习链不读取钢印数据，错过决策模式发现",
            ("T2", "T5"): "记忆积累→学习链传感器：学习链只读传感器，不读MEMORY.md内容做模式发现",
            ("T3", "T5"): "调度反馈→学习链传感器：任务耗时/错误分布数据未被学习链采集",
            ("T5", "T4"): "学习产物坍塌→GC同步：产物坍缩为标签时，需通知GC清理对应MEMORY.md原始段落",
            ("T4", "T5"): "GC归档→学习链传感器：GC丢弃的记录可作为学习链的'遗忘模式'输入",
            ("T1", "T4"): "钢印保真度→GC阈值：高钢印记忆应降低GC丢弃概率",
            ("T3", "T4"): "调度访问频率→GC衰减率：高频访问memory区域应降低衰减率",
            ("T2", "T4"): "记忆存储反馈→GC策略：存储失败/冲突区域应提高GC警惕度",
            ("T5", "T1"): "学习产物→钢印铸造：高置信度产物应触发即时钢印",
            ("T5", "T2"): "学习产物→记忆写入：学习产物的记忆笔记通过适配器写入记忆链",
            ("T5", "T3"): "学习产物的规则修正影响调度参数",
        }

        for e in report["missing"]:
            key = (e["from"], e["to"])
            desc = descriptions.get(key, "")
            pri = priorities.get(key, "P3")
            doc += f"| {e['from']} | {e['to']} | `{e['middleware']}` | {desc} | {pri} |\n"

        doc += "\n## 优先级说明\n\n"
        doc += "- **P0**: 必须立即修复（数据丢失或错误风险）\n"
        doc += "- **P1**: 应在下次梦境期前修复（功能完整性的关键缺口）\n"
        doc += "- **P2**: 功能增强，非阻塞\n"

        output_path = WORKSPACE / "memory" / "chain_coupling_analysis.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(doc, encoding="utf-8")
        print(f"\n📝 报告已写入: {output_path}")
        return output_path


if __name__ == "__main__":
    checker = ChainCouplingChecker()
    report = checker.check_coupling()
    checker.print_report(report)
    checker.save_to_doc(report)
