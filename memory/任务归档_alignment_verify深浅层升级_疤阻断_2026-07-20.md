# 任务归档：alignment_verify 深浅层升级 + 疤阻断机制

**归档时间**：2026-07-20 11:55 GMT+8
**执行人**：TU-8 v5

---

## 任务目标

1. `_check_deep_surface_isolation()` 修复热判断逻辑
2. `cognitive_friction_detector` 修复 `_load()` 白名单过滤
3. HP0 钩子集成：工具失败 → friction registry

---

## 成果

### 1. alignment_verify 深浅层隔离升级

**文件**：`src/alignment_verify.py`

**修改内容**：

#### `_check_deep_surface_isolation()` 疤感知阻断

```
疤查询先于热判断：
  1. 查同类疤（_registry.scar_for_topic）
  2. 疤 ≥ NOTIFY(0.6) → 降低热阻断阈值，有疤也阻断
  3.疤 ≥ ARBITER(0.8) → 直接阻断
  4.疤 < 0.6 → 疤自适应阈值按 0.6 - scar×0.5 计算
  5.热锁（L3）无条件阻断
  6.带宽检查（带宽满载 → 记录疤）
  7.L1热判断：有疤+疤自适应阈值内 → 阻断+auto_surface=True
```

**新字段**：`checks.deep_surface_isolation` 增加 `tension_integral`

#### `_check_deep_surface_isolation()` 热调用修复

```
修复前：tm.get_state()  # 不存在
修复后：tm.check() → ThermalReport
  report.level          → 热等级
  report.tension_integral → 张力积分
  report.recommended_action → 推荐动作
```

**新增前置钩子**：`alignment_verify` 入口新增 `_run_hp0()` → `_run_hp1_before()`

### 2. cognitive_friction_detector 修复

**文件**：`src/cognitive_friction_detector.py`

**`_load()` 白名单过滤修复**：
```python
@dataclass
class FrictionRecord:
    friction_id: str
    friction_type: str
    topic: str
    source: str
    tension: float
    status: str
    created_ts: str = ""
    resolved_ts: str = ""
    tags: list = field(default_factory=list)
```

JSON 加载时用白名单过滤：
```python
white = set(f.name for f in fields(FrictionRecord))
loaded = {k: v for k, v in data.items() if k in white}
```

同时跳过 `status=="suppressed"` 的记录。

### 3. HP0 钩子集成（tool_failure_probe）

**新增文件**：`src/tool_failure_probe.py`（7KB）

**ToolFailureProbe 类**：
- `catch(tool_name, error)`：工具失败时写入 `last_tool_state.json`
- `run_hp0(ctx)`：读取状态 → 注册 friction → 清除状态 → 返回带 `hp0_warnings` 的 ctx
- `flush()`：主动清除状态

**hp0_tool_failure_hook 钩子函数**：
- BEFORE 钩子签名：`fn(ctx) → (proceed, modified_ctx)`
- 调用 `probe.run_hp0(ctx)` 读取上次工具失败
- 返回 `(True, modified_ctx)` — `run_hooks` 自动合并 `hp0_warnings` 到 ctx

**注册**：
```python
hook_injector.register_hook("HP0", HookType.BEFORE,
                             hp0_tool_failure_hook,
                             hook_name="hp0_tool_failure",
                             priority=50)
```

### 4. alignment_verify HP0 集成

**文件**：`src/alignment_verify.py`

**入口顺序**：
```
alignment_verify() 入口
  → HP0（工具失败拦截）[NEW]
  → HP1 BEFORE（可短路）
  → L0/L5 校验
  → HP1 AFTER
```

**`_run_hp0()` 实现**：
```python
def _run_hp0(ctx):
    runner, HT = _get_hp0_runner()  # 延迟加载
    if not runner: return ctx
    try:
        result = runner("HP0", HT.BEFORE, ctx)
        # result = {"results": [(hook_name, hook_result)], ...}
        hook_result = result["results"][0][1]
        ctx.update(hook_result)  # ctx.hp0_warnings = [...]
    except:
        return ctx  # 降级不阻断
    return ctx
```

**ctx 流程**：
```
last_tool_state.json → hp0_tool_failure_hook → hp0_warnings
      → _run_hp0() → ctx["hp0_warnings"]
      → warnings = list(ctx.get("hp0_warnings", []))
      → alignment_verify()["warnings"] 输出
```

---

## 疤机制设计（8.6节 docs/design/ARCHITECTURE_LOG.md）

### 疤叠加公式
```
第N次同类触发：tension_N = base + tension_{N-1} × 0.3
→ 收敛到 base / 0.7 ≈ 1.43× base
```

### 疤反向影响阈值（待实现）

| 疤阈值 | 触发条件 | 响应 |
|--------|---------|------|
|疤 ≥ 0.6 | L1热有疤 | 疤自适应阻断阈值，有疤也阻断 |
|疤 ≥ 0.8 | 任意热等级 | 深度阻断+通知 |
|疤 ≥ 1.43× | 热锁触发线 | 收紧热锁阈值（降低触发温度）|
|疤 ≥ 2× | 带宽检查 | 深层→表层压缩比 100:1→200:1 |
|疤 ≥ 3× | 任意 | 自动卸载最旧的 alignment_overload 疤 |

---

## 测试结果

### alignment_verify 疤感知测试（4/4 通过）

```
A: 无疤+L1热 → passed=True   (无疤+正常热通过)
B: scar=0.70+L1热 → passed=False阻断 (≥NOTIFY(0.6)直接阻断)
C: scar=0.85+L1热 → passed=False阻断 (≥ARBITER(0.8)直接阻断)
D: scar=0.25+L1热 → passed=True   (<0.6疤自适应阈值按0.575通过)
```

### cognitive_friction_detector _load 测试

```
白名单过滤：created_ts 静默异常已消除
suppressed 跳过：suppressed 记录不加载
```

### HP0 钩子测试

```
[A] no prior state: []         ✓ 无状态时无警告
[B] with prior state: ['[HP0] 同类疤已存在 scar=0.25，跳过重复注册']  ✓
friction count: 1             ✓ friction 已注册
```

---

## 文件变更清单

| 文件 | 操作 | 内容 |
|------|------|------|
| `src/alignment_verify.py` | 修改 | `_check_deep_surface_isolation()`疤逻辑+HP0集成 |
| `src/cognitive_friction_detector.py` | 修改 | `_load()`白名单过滤 |
| `src/tool_failure_probe.py` | 新建 | ToolFailureProbe + hp0_tool_failure_hook |
| `src/hook_injector.py` | 修改 | HP0钩子注册 |
| `docs/design/ARCHITECTURE_LOG.md` | 修改 | 8.6节疤机制+HP0集成文档 |

**删除**：`debug_friction.py` / `test_scar_blocking.py` / `test_dream_pipeline.py`

---

## 遗留项

1. **疤反向影响阻断阈值**（疤≥阈值时收紧热锁触发线/带宽配额）— 计划设计已在 ARCHITECTURE_LOG 8.6节记录，待实现
2. **疤突破3×基线时自动卸载** — 待实现
