param(
    [Parameter(Mandatory=$true)]
    [string]$NewPrompt,
    
    [string]$ConfigFile = "C:\Users\qq366410837\.qclaw\openclaw.json"
)

# 修改 systemPromptOverride - Node.js 方案
$node = "D:\Program Files\QClaw\v0.2.22.518\resources\node\node.exe"

$script = @"
const fs = require('fs');
const data = JSON.parse(fs.readFileSync('$ConfigFile'.replace(/\\\\/g,'\\\\'), 'utf8'));
data.agents.list[0].systemPromptOverride = `$NewPrompt;
fs.writeFileSync('$ConfigFile'.replace(/\\\\/g,'\\\\'), JSON.stringify(data, null, 2), 'utf8');
console.log('OK');
"@

& $node -e $script

# 验证
Write-Host "验证: " -NoNewline
& "D:\Program Files\QClaw\v0.2.22.518\resources\node\node.exe" -e "const fs=require('fs'); const d=JSON.parse(fs.readFileSync('C:\\Users\\qq366410837\\.qclaw\\openclaw.json','utf8')); console.log(d.agents.list[0].systemPromptOverride.length)"