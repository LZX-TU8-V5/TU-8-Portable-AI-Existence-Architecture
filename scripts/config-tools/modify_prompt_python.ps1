param(
    [Parameter(Mandatory=$true)]
    [string]$NewPrompt,
    
    [string]$ConfigFile = "C:\Users\qq366410837\.qclaw\openclaw.json"
)

# 修改 systemPromptOverride - Python 方案
python -c @"
import json
with open(r'$ConfigFile', 'r', encoding='utf-8') as f:
    config = json.load(f)
config['agents'][0]['list'][0]['systemPromptOverride'] = '''$NewPrompt'''
with open(r'$ConfigFile', 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print('OK')
"@

# 验证
python -c "import json; print(json.load(open(r'$ConfigFile','r',encoding='utf-8'))['agents'][0]['list'][0]['systemPromptOverride'][:50])"