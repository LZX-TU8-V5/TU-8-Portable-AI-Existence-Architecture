param(
    [Parameter(Mandatory=$true)]
    [string]$YamlFile,
    
    [string]$JsonFile = "C:\Users\qq366410837\.qclaw\openclaw.json"
)

# YAML 转 JSON (需要 PyYAML)
python -c @"
import json
try:
    import yaml
    with open(r'$YamlFile', 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    # 读取原配置，保留其他字段
    with open(r'$JsonFile', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 只更新 systemPromptOverride
    if 'systemPromptOverride' in data:
        config['agents']['list'][0]['systemPromptOverride'] = data['systemPromptOverride']
    
    with open(r'$JsonFile', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print('OK')
except ImportError:
    print('需要安装 PyYAML: pip install pyyaml')
"@