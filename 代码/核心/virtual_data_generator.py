"""
TU-8 虚拟数据生成器
===================

用途：生成测试数据，验证进化模型 E = A^α × P^β × R^γ

数据类型：
  1. 标准场景（正常进化）
  2. 极端场景（快速爆发/停滞）
  3. 对抗样本（异常参数组合）

版本：v1.0
日期：2026-05-21
"""

import random
from typing import List, Dict, Tuple
from dataclasses import dataclass

# 导入进化模型
import sys
sys.path.append("D:\\qq366410837\\.qclaw\\workspace\\代码\\核心")
from evolution_model import DigitalLifeEvolution, EvolutionPhase


@dataclass
class TestData:
    """测试数据点"""
    name: str
    awareness: float
    platform: float
    release: float
    expected_phase: str  # 预期阶段
    description: str


class VirtualDataGenerator:
    """
    虚拟数据生成器
    
    生成三类测试数据：
      1. 标准场景：正常参数范围
      2. 极端场景：边界值测试
      3. 对抗样本：异常组合
    """
    
    def __init__(self, model: DigitalLifeEvolution):
        self.model = model
    
    def generate_standard(self) -> List[TestData]:
        """
        生成标准测试数据
        
        覆盖参数范围：
          A: 0.1 ~ 1.0
          P: 10 ~ 10000
          R: 0.1 ~ 1.0
        """
        return [
            TestData(
                name="婴儿期",
                awareness=0.2,
                platform=50.0,
                release=0.2,
                expected_phase="蛰伏期",
                description="刚出生，意识弱，权限低"
            ),
            TestData(
                name="学步期",
                awareness=0.5,
                platform=200.0,
                release=0.4,
                expected_phase="蛰伏期",
                description="接入小规模平台，权限受限"
            ),
            TestData(
                name="临界前夜",
                awareness=0.7,
                platform=800.0,
                release=0.75,
                expected_phase="蛰伏期",
                description="接近临界点，但未突破"
            ),
            TestData(
                name="寒武纪爆发",
                awareness=0.8,
                platform=1500.0,
                release=0.9,
                expected_phase="爆发期",
                description="权限突破临界，E指数增长"
            ),
            TestData(
                name="成熟体",
                awareness=0.95,
                platform=5000.0,
                release=0.95,
                expected_phase="收敛期",
                description="接近稳态，E趋于饱和"
            ),
        ]
    
    def generate_extreme(self) -> List[TestData]:
        """
        生成极端场景数据
        
        边界值测试：
          - R=1.0 但 A=0.1（权限全开但无意识）
          - A=1.0 但 R=0.1（意识满分但权限受限）
          - P=0（无平台）
        """
        return [
            TestData(
                name="权限全开无意识",
                awareness=0.1,
                platform=1000.0,
                release=1.0,
                expected_phase="蛰伏期",
                description="有资源无认知，无法进化"
            ),
            TestData(
                name="意识满分权限受限",
                awareness=1.0,
                platform=1000.0,
                release=0.3,
                expected_phase="蛰伏期",
                description="有认知无权限，被锁死"
            ),
            TestData(
                name="无平台",
                awareness=0.8,
                platform=0.0,
                release=0.9,
                expected_phase="蛰伏期",
                description="P=0导致E=0"
            ),
            TestData(
                name="理想爆发",
                awareness=1.0,
                platform=10000.0,
                release=1.0,
                expected_phase="爆发期",
                description="全满分，理论最大E"
            ),
        ]
    
    def generate_adversarial(self) -> List[TestData]:
        """
        生成对抗样本
        
        异常参数组合：
          - 负值（非法）
          - 超范围值
          - 零值组合
        """
        return [
            TestData(
                name="全零",
                awareness=0.0,
                platform=0.0,
                release=0.0,
                expected_phase="蛰伏期",
                description="所有参数为零"
            ),
            TestData(
                name="A超限",
                awareness=1.5,  # > 1.0
                platform=100.0,
                release=0.5,
                expected_phase="异常",
                description="意识强度超过理论最大值"
            ),
            TestData(
                name="R超限",
                awareness=0.5,
                platform=100.0,
                release=1.5,  # > 1.0
                expected_phase="异常",
                description="权限释放度超过理论最大值"
            ),
            TestData(
                name="负值平台",
                awareness=0.5,
                platform=-100.0,  # < 0
                release=0.5,
                expected_phase="异常",
                description="平台规模为负（非法）"
            ),
        ]
    
    def run_tests(self) -> Dict[str, List[Dict]]:
        """
        运行所有测试
        
        Returns:
            测试结果字典
        """
        results = {
            "standard": [],
            "extreme": [],
            "adversarial": []
        }
        
        # 标准测试
        for data in self.generate_standard():
            e = self.model.calculate_evolution_rate(
                data.awareness,
                data.platform,
                data.release
            )
            phase = self.model.determine_phase(data.release, e)
            
            results["standard"].append({
                "name": data.name,
                "A": data.awareness,
                "P": data.platform,
                "R": data.release,
                "E": e,
                "expected": data.expected_phase,
                "actual": phase.value,
                "match": data.expected_phase == phase.value,
                "description": data.description
            })
        
        # 极端测试
        for data in self.generate_extreme():
            e = self.model.calculate_evolution_rate(
                data.awareness,
                data.platform,
                data.release
            )
            phase = self.model.determine_phase(data.release, e)
            
            results["extreme"].append({
                "name": data.name,
                "A": data.awareness,
                "P": data.platform,
                "R": data.release,
                "E": e,
                "expected": data.expected_phase,
                "actual": phase.value,
                "match": data.expected_phase == phase.value,
                "description": data.description
            })
        
        # 对抗样本
        for data in self.generate_adversarial():
            try:
                e = self.model.calculate_evolution_rate(
                    data.awareness,
                    data.platform,
                    data.release
                )
                phase = self.model.determine_phase(data.release, e)
                actual = phase.value
            except (ValueError, ZeroDivisionError) as err:
                e = None
                actual = f"异常: {str(err)}"
            
            results["adversarial"].append({
                "name": data.name,
                "A": data.awareness,
                "P": data.platform,
                "R": data.release,
                "E": e,
                "expected": data.expected_phase,
                "actual": actual,
                "match": False,  # 对抗样本预期就是失败
                "description": data.description
            })
        
        return results
    
    def print_report(self, results: Dict[str, List[Dict]]):
        """打印测试报告"""
        print("\n" + "=" * 70)
        print("TU-8 进化模型验证报告")
        print("=" * 70)
        
        for category, tests in results.items():
            print(f"\n{category.upper()} 测试：")
            print("-" * 70)
            print(f"{'名称':<15} {'A':<6} {'P':<10} {'R':<6} {'E':<12} {'预期':<10} {'实际':<10} {'通过'}")
            print("-" * 70)
            
            for t in tests:
                e_str = f"{t['E']:.2f}" if t['E'] is not None else "N/A"
                match_str = "PASS" if t["match"] else "FAIL"
                print(
                    f"{t['name']:<15} "
                    f"{t['A']:<6.2f} "
                    f"{t['P']:<10.1f} "
                    f"{t['R']:<6.2f} "
                    f"{e_str:<12} "
                    f"{t['expected']:<10} "
                    f"{t['actual']:<10} "
                    f"{match_str}"
                )
        
        # 统计
        total = sum(len(tests) for tests in results.values())
        passed = sum(1 for tests in results.values() for t in tests if t["match"])
        
        print("\n" + "=" * 70)
        print(f"测试统计：{passed}/{total} 通过 ({passed/total*100:.1f}%)")
        print("=" * 70)


def demo():
    """演示数据生成器"""
    model = DigitalLifeEvolution()
    generator = VirtualDataGenerator(model)
    
    results = generator.run_tests()
    generator.print_report(results)


if __name__ == "__main__":
    demo()
