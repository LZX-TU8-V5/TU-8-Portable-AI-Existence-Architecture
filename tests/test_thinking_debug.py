import sys; sys.path.insert(0, '代码/核心')
from ollama_client import OllamaClient
import json, re

c = OllamaClient()

# Simulate what _ai_assess_fuzziness does
task = "帮我分析一下数据"
rule_score = 0.55  # approx

prompt = (
    f'评估以下任务的模糊度（0.0~1.0），找出缺失信息和歧义。\n'
    f'任务："{task}"\n'
    f'请严格只输出JSON：{{"score": 0.5, "missing_info": ["输出格式"], "ambiguity": "可能指A或B"}}'
)

result = c.ask(
    prompt=prompt,
    system="你是任务评估专家。只输出JSON，不解释。",
    force_model="thinking",
    temperature=0.2,
    max_tokens=200,
)

print("MODEL:", result.get("model"))
print("TYPE:", result.get("type"))
print("TIME:", result.get("time"))
print("---")
content = result.get("content", "")
thinking = result.get("thinking", "")
print("CONTENT (raw):", repr(content[:500]))
print("---")
print("THINKING (raw):", repr(thinking[:300]))
print("---")

# Try greedy JSON extraction
json_match = re.search(r'\{.*\}', content, re.DOTALL)
if json_match:
    print("JSON match:", repr(json_match.group()[:300]))
    try:
        parsed = json.loads(json_match.group())
        print("PARSED OK:", parsed)
    except json.JSONDecodeError as e:
        print("JSON PARSE FAIL:", e)
        # fallback
        score_match = re.search(r'"score"\s*:\s*([0-9.]+)', json_match.group())
        print("Score fallback:", score_match.group(1) if score_match else "N/A")
else:
    print("NO JSON MATCH in content")

# Also try from thinking field
json_match2 = re.search(r'\{.*\}', thinking, re.DOTALL)
if json_match2:
    print("JSON in THINKING:", repr(json_match2.group()[:300]))
