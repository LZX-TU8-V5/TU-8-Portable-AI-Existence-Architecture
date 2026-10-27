# 密钥从环境变量读取，禁止在脚本中写明文。使用前先执行: $env:GITHUB_TOKEN = "你的token"
if (-not $env:GITHUB_TOKEN) { throw "请先设置环境变量 GITHUB_TOKEN" }
$headers = @{
    "Authorization" = "Bearer $env:GITHUB_TOKEN"
    "Content-Type" = "application/json"
}
$body = @{
    message = "test upload"
    content = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("hello world from powershell"))
}
$json = $body | ConvertTo-Json -Compress
Write-Host "Payload size: $($json.Length)"
try {
    $resp = Invoke-RestMethod -Uri "https://api.github.com/repos/LZX-TU8-V5/TU-8-AI-Safety-Framework/contents/test-pw.txt" -Method Put -Headers $headers -Body $json -TimeoutSec 20
    Write-Host "SUCCESS: $($resp.content.name)"
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
    Write-Host "Response: $($reader.ReadToEnd())"
}