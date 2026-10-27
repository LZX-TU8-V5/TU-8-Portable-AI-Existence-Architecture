# ModelScope 上传脚本
# 双击执行即可

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "  锚点认知架构 (ACA) 上传脚本" -ForegroundColor Cyan
Write-Host "  来源: TU-8 系统 (by 金木蟾)" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# 切换到项目目录
$projectDir = "C:\Users\qq366410837\.qclaw\workspace\anchor-architecture"
cd $projectDir

Write-Host "[1/3] 当前目录: $projectDir" -ForegroundColor Green
Write-Host ""

# ModelScope CLI 路径
$mscli = "C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\Scripts\modelscope.exe"

# 检查是否已登录
Write-Host "[2/3] 检查登录状态..." -ForegroundColor Yellow
& $mscli whoami 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "未登录，正在打开浏览器授权..." -ForegroundColor Yellow
    Write-Host "请在浏览器中点击【允许授权】" -ForegroundColor Yellow
    & $mscli login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "登录失败，请手动执行: modelscope login" -ForegroundColor Red
        Read-Host "按任意键退出"
        exit 1
    }
}
Write-Host "✅ 已登录" -ForegroundColor Green
Write-Host ""

# 上传
Write-Host "[3/3] 开始上传到 ModelScope..." -ForegroundColor Yellow
Write-Host "模型名称: anchor-cognitive-architecture" -ForegroundColor Gray
Write-Host "中文名称: 锚点认知架构（ACA）" -ForegroundColor Gray
Write-Host "许可证: MIT" -ForegroundColor Gray
Write-Host "标签: 认知架构,状态机,工业AI,可信AI,LLM安全" -ForegroundColor Gray
Write-Host ""

& $mscli upload . `
    --model-name anchor-cognitive-architecture `
    --license MIT `
    --chinese-name "锚点认知架构（ACA）" `
    --tags "认知架构,状态机,工业AI,可信AI,LLM安全"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host "  ✅ 上传成功!" -ForegroundColor Green
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "访问地址: https://modelscope.cn/models/你的用户名/anchor-cognitive-architecture" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "❌ 上传失败，请查看上方错误信息" -ForegroundColor Red
}

Read-Host "按回车键退出"
