import sys; sys.path.insert(0, '代码/核心')
from ollama_client import OllamaClient
c = OllamaClient()
prompt = '评估任务模糊度。任务："帮我搞一下"。输出JSON: {"score": 0.7, "missing_info": ["输出格式"], "ambiguity": "可能指A或B"}'
result = c.think(prompt, system='你是评估专家。只输出JSON。')
print('CONTENT:', repr(result.get('content', '')[:300]))
print('THINKING:', repr(result.get('thinking', '')[:200]))
