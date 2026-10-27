# 密钥从环境变量读取，禁止在脚本中写明文。使用前先执行: $env:GITHUB_TOKEN = "你的token"
if (-not $env:GITHUB_TOKEN) { throw "请先设置环境变量 GITHUB_TOKEN" }
$headers = @{
    "Authorization" = "Bearer $env:GITHUB_TOKEN"
    "Content-Type" = "application/json"
    "Accept" = "application/vnd.github.v3+json"
}
$body = @{
    name = "TU-8-v1.2"
    description = "TU-8 AI Safety Framework v1.2 - L0 Existential Gene (5-layer DNA architecture: L0-L5) for AI safety and alignment. CC BY-SA 4.0"
    private = $false
    auto_init = $false
}
$json = $body | ConvertTo-Json -Compress
try {
    $resp = Invoke-RestMethod -Uri "https://api.github.com/user/repos" -Method Post -Headers $headers -Body $json -TimeoutSec 20
    Write-Host "CREATED: $($resp.html_url)"
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    try {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        Write-Host "Response: $($reader.ReadToEnd())"
    } catch {}
}