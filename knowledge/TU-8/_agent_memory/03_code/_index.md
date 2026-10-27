# 03_code — 代码资产

> 可执行的Python文件。运行前确保Python 3.13+ 环境可用。

## 文件清单

| 文件 | 行数 | 用途 | 测试状态 |
|------|------|------|---------|
| `sanitization_layer.py` | ~900 | 脱敏层：同形字映射、语义稀释、三级钢印体系 | ✅ test_all()全过 |
| `tu8_dispatcher.py` | ~800 | 调度器：云端调用前自动脱敏、A+A+A决策链 | 待测试 |
| `__pycache__/` | - | Python编译缓存（自动生成，勿提交） | - |

## 快速测试

```powershell
# 测试脱敏层
python -c "import sys; sys.path.insert(0,'.'); import sanitization_layer; sanitization_layer.test_all()"

# 编译检查（不运行）
python -m py_compile sanitization_layer.py
```

## 关联配置
- `sanitization_layer.py` ↔ `../02_config/sanitization_rules.json`
- `tu8_dispatcher.py` ↔ `../02_config/sanitization_rules.json`

## 注意事项
- `.pyc` 缓存文件由Python自动生成，无需手动管理
- `__pycache__/` 不应提交到版本控制
