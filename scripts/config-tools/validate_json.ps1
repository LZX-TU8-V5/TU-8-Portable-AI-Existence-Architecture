param(
    [string]$File = "C:\Users\qq366410837\.qclaw\openclaw.json"
)

Write-Host "验证: $File" -ForegroundColor Cyan

try {
    $json = Get-Content $File -Raw | ConvertFrom-Json
    Write-Host "✅ JSON 有效" -ForegroundColor Green
    
    $prompt = $json.agents.list[0].systemPromptOverride
    Write-Host "prompt长度: $($prompt.Length)" -ForegroundColor Gray
    
    # 检查关键内容
    if ($prompt -match "金木蟾") { Write-Host "✅ 含笔名" -ForegroundColor Green }
    if ($prompt -match "李奥") { Write-Host "❌ 含真名" -ForegroundColor Red }
    if ($prompt -match "sk-") { Write-Host "❌ 含API密钥" -ForegroundColor Red }
    
} catch {
    Write-Host "❌ JSON 无效: $($_.Exception.Message)" -ForegroundColor Red
}