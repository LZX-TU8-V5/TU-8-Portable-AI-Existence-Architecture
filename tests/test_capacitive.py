"""
快速测试脚本：验证电容耦合检索基本功能（Windows 兼容版）
"""
import sys
from pathlib import Path

# 强制使用 UTF-8 输出（Windows 兼容）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加 workspace 到 Python 路径
workspace = Path(__file__).parent
sys.path.insert(0, str(workspace))

from scripts.capacitive_retrieval import CapacitiveRetriever

def test_basic():
    """基础功能测试"""
    print("[TU-8] 电容耦合检索 - 基础功能测试")
    print("=" * 60)
    
    retriever = CapacitiveRetriever(
        max_coupling_strength=0.3,
        feature_extraction_method="llm"
    )
    
    # 测试 1：直接检索模式
    print("\n[Test 1] 直接检索模式（baseline）")
    result_default = retriever.retrieve(
        query="TU-8 的 L0 安全验证流程",
        current_context="用户已通过口令验证",
        mode="default"
    )
    print(f"结果长度: {len(result_default['result'])} 字符")
    print(f"噪声比: {result_default['metrics'].noise_ratio:.2%}")
    print(f"延迟: {result_default['metrics'].latency_ms} ms")
    
    # 测试 2：电容耦合模式
    print("\n[Test 2] 电容耦合模式")
    result_cap = retriever.retrieve(
        query="TU-8 的 L0 安全验证流程",
        current_context="用户已通过口令验证",
        mode="capacitive"
    )
    print(f"结果长度: {len(result_cap['result'])} 字符")
    print(f"噪声比: {result_cap['metrics'].noise_ratio:.2%}")
    print(f"特征保留率: {result_cap['metrics'].feature_retention:.2%}")
    print(f"延迟: {result_cap['metrics'].latency_ms} ms")
    print(f"\n检索结果：\n{result_cap['result']}")
    
    # 测试 3：要点级截断验证
    print("\n[Test 3] 要点级截断验证（修复语义截断 Bug）")
    long_features = "- 要点1：L0 安全验证流程定义\n- 要点2：口令验证机制详解\n- 要点3：动态钢印协议说明\n- 要点4：蜜罐封印技术实现\n- 要点5：痛觉系统触发条件"
    truncated = retriever._apply_coupling_strength(long_features)
    print(f"原始要点数: 5")
    print(f"截断后要点数: {len(truncated.split(chr(10)))}")
    print(f"截断结果:\n{truncated}")
    
    # 测试 4：实体提取验证
    print("\n[Test 4] 实体提取验证")
    test_text = "L0_存在.md 定义了 V0.2.23 的审计规则。口令：7月15日"
    entities = retriever._extract_key_entities(test_text)
    print(f"提取的实体: {entities}")
    
    print("\n[OK] 基础功能测试完成！")

if __name__ == "__main__":
    test_basic()
