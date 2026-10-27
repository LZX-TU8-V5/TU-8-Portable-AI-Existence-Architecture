"""P0模块接入v3.0集成测试"""
import sys
sys.path.insert(0, '代码/核心')
sys.path.insert(0, '代码/认知')

# Test routing_engine AI availability
from routing_engine import _get_ollama_client, AI_ROUTING_ENABLED, AI_CONFIDENCE_THRESHOLD
client = _get_ollama_client()
print(f"Routing Engine: Ollama={client is not None}, AI_ENABLED={AI_ROUTING_ENABLED}, CONF_THRESHOLD={AI_CONFIDENCE_THRESHOLD}")

# Test intent_clarifier AI availability
from intent_clarifier import _get_ollama_client as ic_get_client, AI_CLARIFY_ENABLED
client2 = ic_get_client()
print(f"Intent Clarifier: Ollama={client2 is not None}, AI_ENABLED={AI_CLARIFY_ENABLED}")

# Test rule-only routing (no AI)
from routing_engine import Router
router = Router()

queries = ["那个怎么弄", "v5锚点是什么", "帮我看看这个", "分析一下架构问题"]
for q in queries:
    domains_rule = router._guess_domain_from_query(q, use_ai=False)
    domains_ai = router._guess_domain_from_query(q, use_ai=True)
    improved = "UP" if len(domains_ai) > len(domains_rule) else "SAME"
    print(f"  [{q}] rule={domains_rule} ai={domains_ai} {improved}")

# Test rule-only fuzziness
from intent_clarifier import assess_fuzziness
fuzz = assess_fuzziness("帮我搞一下", use_ai=False)
print(f"Rule-only [帮我搞一下]: {fuzz['score']:.0%} ({fuzz['level']})")

# Test AI-enhanced fuzziness
fuzz_ai = assess_fuzziness("帮我分析一下数据", use_ai=True)
print(f"AI-enhanced [帮我分析一下数据]: {fuzz_ai['score']:.0%} ({fuzz_ai['level']}) ai={fuzz_ai.get('ai_enhanced', False)}")

# Test AI-enhanced 3Q
from intent_clarifier import generate_3q
q_template = generate_3q("帮我搞一下", use_ai=False)
q_ai = generate_3q("帮我搞一下", use_ai=True)
print(f"Template 3Q: {q_template[:60]}...")
print(f"AI 3Q: {q_ai[:60] if q_ai else 'N/A'}...")

# Degradation test (AI=False)
fuzz_no_ai = assess_fuzziness("帮我搞一下", use_ai=False)
print(f"Degration test: use_ai=False works, score={fuzz_no_ai['score']:.0%}")

print("\n[P0 Integration Test Complete]")
