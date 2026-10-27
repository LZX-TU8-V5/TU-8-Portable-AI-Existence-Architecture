# 密钥从环境变量读取，禁止在脚本中写明文。使用前先执行: $env:GITHUB_TOKEN = "你的token"
if (-not $env:GITHUB_TOKEN) { throw "请先设置环境变量 GITHUB_TOKEN" }
$headers = @{
    "Authorization" = "Bearer $env:GITHUB_TOKEN"
    "Content-Type" = "application/json"
    "Accept" = "application/vnd.github.v3+json"
}
$body = @{
    message = "test"
    content = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("test"))
}
$json = $body | ConvertTo-Json -Compress
try {
    $resp = Invoke-WebRequest -Uri "https://api.github.com/repos/LZX-TU8-V5/TU-8-AI-Safety-Framework/contents/test.txt" -Method Put -Headers $headers -Body $json -TimeoutSec 20
    Write-Host "Status: $($resp.StatusCode)"
    Write-Host "Headers:"
    $resp.Headers | Format-Table Name, Value
} catch {
    Write-Host "ERROR: $($_.Exception.Message)"
    Write-Host "Status Code: $($_.Exception.Response.StatusCode)"
    Write-Host "Description: $($_.Exception.Response.StatusDescription)"
    try {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        Write-Host "Response Body: $($reader.ReadToEnd())"
    } catch {}
}