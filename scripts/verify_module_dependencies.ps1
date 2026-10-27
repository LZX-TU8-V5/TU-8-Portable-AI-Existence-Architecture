# 模块依赖验证脚本
# 检查所有模块的 import 链接

$workspace = "C:\Users\qq366410837\.qclaw\workspace\src"
$errors = @()
$warnings = @()
$checked = @{}

# 获取所有 Python 文件
$files = Get-ChildItem "$workspace\*.py" | Where-Object { $_.Name -notlike "test_*" }

Write-Host "检查 $($files.Count) 个模块..." -ForegroundColor Cyan

foreach ($file in $files) {
    $moduleName = $file.BaseName
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    
    # 提取 import 语句
    $imports = [regex]::Matches($content, '(?:from|import)\s+(\w+)') | ForEach-Object { $_.Groups[1].Value }
    
    # 标准库白名单
    $stdlib = @('json', 'os', 'time', 'math', 'logging', 'sys', 're', 'datetime', 'collections', 'pathlib', 'typing', 'dataclasses', 'enum', 'functools', 'itertools', 'copy', 'hashlib', 'random', 'threading', 'subprocess', 'io', 'csv', 'glob', 'abc', 'contextlib', 'warnings', 'traceback', 'inspect', 'ast')
    
    # 第三方库白名单
    $thirdparty = @('numpy', 'pandas', 'scipy', 'sklearn', 'torch', 'tensorflow', 'requests', 'httpx', 'aiohttp')
    
    # 检查本地模块导入
    $localImports = $imports | Where-Object { $_ -notin $stdlib -and $_ -notin $thirdparty }
    
    # 已知模块列表
    $knownModules = Get-ChildItem "$workspace\*.py" | ForEach-Object { $_.BaseName }
    
    foreach ($imp in $localImports) {
        if ($imp -notin $knownModules) {
            $errors += "[$moduleName] 导入不存在的模块: $imp"
        }
    }
    
    $checked[$moduleName] = $localImports
}

# 检测循环依赖
foreach ($mod in $checked.Keys) {
    $imports = $checked[$mod]
    foreach ($imp in $imports) {
        if ($checked.ContainsKey($imp)) {
            $impImports = $checked[$imp]
            if ($mod -in $impImports) {
                $warnings += "循环依赖: $mod <-> $imp"
            }
        }
    }
}

# 检查状态文件
$agentDir = "C:\Users\qq366410837\.qclaw\workspace\_agent_memory"
$stateFiles = @(
    "surface_tension_state.json",
    "phase_lock_state.json",
    "attractor_basin_state.json",
    "intrinsic_reward_state.json",
    "heartbeat_state.json"
)

Write-Host "`n检查状态文件..." -ForegroundColor Cyan
foreach ($sf in $stateFiles) {
    $path = "$agentDir\$sf"
    if (Test-Path $path) {
        Write-Host "  OK $sf" -ForegroundColor Green
    } else {
        Write-Host "  -- $sf (未创建)" -ForegroundColor Yellow
    }
}

# 输出结果
Write-Host "`n========== 验证结果 ==========" -ForegroundColor Cyan
Write-Host "错误: $($errors.Count)" -ForegroundColor $(if ($errors.Count -gt 0) { "Red" } else { "Green" })
Write-Host "警告: $($warnings.Count)" -ForegroundColor $(if ($warnings.Count -gt 0) { "Yellow" } else { "Green" })

if ($errors.Count -gt 0) {
    Write-Host "`n错误详情:" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  $_" }
}

if ($warnings.Count -gt 0) {
    Write-Host "`n警告详情:" -ForegroundColor Yellow
    $warnings | ForEach-Object { Write-Host "  $_" }
}

Write-Host "`n统计: 已检查模块 $($files.Count)" -ForegroundColor Cyan
