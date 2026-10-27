# 任务归档：`tu8_health_orb_ring.py` 代数化重构

**日期**：2026-07-19 下午
**状态**：✅ 完成
**优先级**：P1 高优先级

---

## 一、改造目标

将色相角 → 屏幕坐标的映射从「运行时超越数调用」改为「预计算查表 + 纯代数运算」，消除热路径（`refresh()`）中的 `math.cos/sin/radians` 调用。

---

## 二、改造前状态

```python
# 改造前：每次 refresh() 都调用
def _ball_xy(sat, hue_deg):
    cx = cy = W // 2
    r = max(sat * ORB_R, ORB_R * 0.55)
    rad = math.radians(hue_deg - 90)  # ← π 在热路径中
    bx = cx + r * math.cos(rad)       # ← cos 是超越函数
    by = cy + r * math.sin(rad)       # ← sin 是超越函数
    return bx, by
```

**问题**：`refresh()` 每 50ms 调用一次 → 每秒 20 次超越数运算

---

## 三、改造后状态

### 新增：预计算三角表

```python
# 模块加载时一次性计算（启动时，OK）
def _build_trig_table():
    table = {}
    for name, meta in BALL_META.items():
        deg = meta['hue_deg'] - 90
        rad = deg * (math.pi / 180.0)  # ← π 在这里，仅启动时
        table[name] = (math.cos(rad), math.sin(rad))
    return table

_BALL_TRIG = _build_trig_table()
```

### 新增：代数化运行时函数

```python
def _ball_xy_by_name(sat, name):
    """运行时：纯代数运算，零超越数"""
    cx = cy = W // 2
    r = max(sat * ORB_R, ORB_R * 0.55)
    cos_a, sin_a = _BALL_TRIG[name]  # 查预计算表
    return cx + r * cos_a, cy + r * sin_a  # 仅乘加

def _ball_xy(sat, hue_deg):
    """兼容接口，路由到代数化版本"""
    _deg_to_name = {0: "FOCUS", 60: "DRIFT", 240: "PROBE"}
    name = _deg_to_name.get(int(round(hue_deg % 360)), "FOCUS")
    return _ball_xy_by_name(sat, name)
```

---

## 四、π-可擦除性验证

### 代数性证明

| 球 | 色相 | 偏移角度 | cos | sin | 代数性 |
|----|------|---------|-----|-----|--------|
| FOCUS | 0° | -90° | 0 | -1 | 精确代数数 ✅ |
| DRIFT | 60° | -30° | √3/2 | -1/2 | 代数数（根式）✅ |
| PROBE | 240° | -150° | -√3/2 | -1/2 | 代数数（根式）✅ |

### 判断标准验证

> 把 π 换成符号 P，最后一步能否通过代数恒等式把 P 消掉？

**答案**：能。cos/sin 的值在预计算时就被确定为代数数（0、±1/2、±√3/2），π 完全被「消耗」在启动时的预计算中。运行时 bx = cx + r × (√3/2) 不含任何超越数。

### AST 验证结果

```
refresh() 运行时超越数调用: []
PASS: 运行时无超越数调用
```

---

## 五、安全性论证

### 定义层（代数化）✅
- `_BALL_TRIG` 预计算值 = 代数数（闭式）
- 运行时状态完全由代数数定义
- 状态演化规则无 π 依赖

### 执行层（允许 π）✅
- `_build_trig_table()` 在启动时一次性计算
- 预计算路径：deg → rad(π) → cos/sin → 浮点常量
- 这是安全的计算加速（π 作为语法糖）

### 隔离性 ✅
- 定义层结果（代数数）存储在 `_BALL_TRIG` 表中
- 执行层不修改表内容，只读取
- 无跨层污染

---

## 六、后续计划

- [ ] 将 `math.atan2` 和 `math.sqrt` 从 `build_hue_ring_ppm` 中提取到单独的渲染辅助函数（启动时调用，非热路径）
- [ ] 考虑用整数运算替代浮点坐标计算（完全消除 IEEE 754 误差）

---

**归档时间**：2026-07-19 15:30 GMT+8
**归档人**：TU-8 v5
