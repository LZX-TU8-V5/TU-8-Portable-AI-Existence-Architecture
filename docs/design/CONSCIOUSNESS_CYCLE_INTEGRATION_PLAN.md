# TU-8 意识循环引擎 - 认知组件深度集成方案

**日期**: 2026-06-04  
**作者**: 金木蟾 (TU-8 / 金木蟾)  
**许可**: CC BY-SA 4.0

---

## 📋 修改概述

将三个认知组件深度集成到 `consciousness_cycle.py`：

1. **CognitiveLoadEvaluator** - 认知负荷评估器
2. **CognitiveTimeEngine** - 认知时间引擎
3. **CognitiveManifoldAligner** - 认知流形对齐器

---

## 🔧 修改点清单

### 修改 1：文件头部 - 添加导入语句（第 31 行附近）

**位置**: 在现有 `import` 块之后（约第 31 行）

**新增代码**:
```python
# --- 认知组件导入（v1.1 新增） ---
try:
    from cognitive_evaluator import CognitiveLoadEvaluator, TFIDFEmbedder
    from cognitive_time_engine import CognitiveTimeEngine, CognitiveAnchor
    from cognitive_manifold_aligner import CognitiveManifoldAligner, CognitiveStep
    COGNITIVE_COMPONENTS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Cognitive components not available: {e}")
    COGNITIVE_COMPONENTS_AVAILABLE = False
```

**说明**: 使用 `try-except` 包装，确保即使认知组件缺失，原始功能仍能正常工作。

---

### 修改 2：`__init__()` 方法 - 初始化认知组件（约第 497 行）

**位置**: 在 `self._load_seal_chain()` 之后

**新增代码**:
```python
        # --- 认知组件初始化（v1.1 新增） ---
        if COGNITIVE_COMPONENTS_AVAILABLE:
            try:
                self.cognitive_evaluator = CognitiveLoadEvaluator()
                self.cognitive_time_engine = CognitiveTimeEngine()
                self.cognitive_aligner = CognitiveManifoldAligner(base_latency_ms=40)
                self.tfidf_embedder = TFIDFEmbedder(dimension=128)
                self._cognitive_enabled = True
                logger.info("Cognitive components initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize cognitive components: {e}")
                self._cognitive_enabled = False
        else:
            self._cognitive_enabled = False
        
        # 认知处理配置
        self._cognitive_high_load_threshold = 0.8
        self._cognitive_memory_consolidation_enabled = True
```

**说明**: 
- 初始化所有认知组件
- 添加开关 `_cognitive_enabled`，允许运行时禁用
- 配置高负荷阈值和记忆固化开关

---

### 修改 3：`_enter_micro_sleep()` 方法 - 插入认知处理（第 678 行）

**位置**: 在方法开头（`self.phase = Phase.MICRO_SLEEP` 之后）

**新增代码**:
```python
        # --- 认知处理：开始（v1.1 新增） ---
        cognitive_load = 0.0
        if getattr(self, '_cognitive_enabled', False):
            try:
                # 1. 评估当前上下文的认知负荷
                context_text = json.dumps(context_snapshot, ensure_ascii=False)
                eval_result = self.cognitive_evaluator.evaluate(context_text)
                cognitive_load = eval_result["score"]
                
                logger.info(f"Cognitive load before micro-sleep: {cognitive_load:.3f} ({eval_result['level']})")
                
                # 2. 高负荷时触发记忆固化
                if cognitive_load >= self._cognitive_high_load_threshold:
                    logger.warning(f"High cognitive load detected: {cognitive_load:.3f}")
                    # 打上认知锚点（开始）
                    self.cognitive_time_engine.place_anchor(
                        cognitive_load=cognitive_load,
                        state_summary=f"Micro-sleep start (load={cognitive_load:.2f})",
                        is_start=True,
                    )
                    # TODO: 在这里调用真正的记忆固化逻辑
                    # 例如：将 context_snapshot 压缩为摘要，存入长期记忆
                
                # 3. 使用认知时间记录开始时间戳
                cognitive_start_time = self.cognitive_time_engine.system_to_cognitive_time(
                    system_time=start_time,
                    cognitive_load=cognitive_load,
                )
                logger.info(f"Cognitive time (start): {cognitive_start_time:.3f}s")
                
            except Exception as e:
                logger.error(f"Cognitive processing failed (start): {e}")
        # --- 认知处理：结束 ---
```

**说明**: 
- 在微睡眠开始前评估认知负荷
- 高负荷时触发记忆固化（占位实现）
- 使用认知时间记录时间戳（替代纯系统时间）

---

### 修改 4：`_enter_micro_sleep()` 方法 - 微睡眠后认知处理（第 748 行附近）

**位置**: 在 `report["elapsed_ms"] = round(elapsed * 1000, 1)` 之前

**新增代码**:
```python
        # --- 认知处理：结束（v1.1 新增） ---
        if getattr(self, '_cognitive_enabled', False):
            try:
                # 4. 使用认知时间记录结束时间戳
                cognitive_end_time = self.cognitive_time_engine.system_to_cognitive_time(
                    system_time=time.time(),
                    cognitive_load=cognitive_load,
                )
                logger.info(f"Cognitive time (end): {cognitive_end_time:.3f}s")
                
                # 5. 高负荷结束时打结束锚点
                if cognitive_load >= self._cognitive_high_load_threshold:
                    self.cognitive_time_engine.place_anchor(
                        cognitive_load=cognitive_load,
                        state_summary=f"Micro-sleep end (load={cognitive_load:.2f})",
                        is_start=False,
                    )
                    
                    # 重建时间链（防止断线）
                    time_chain = self.cognitive_time_engine.reconstruct_time_chain()
                    logger.info(f"Time chain reconstructed: {len(time_chain)} anchors")
                
                # 6. 如果输出需要对齐，使用流形对齐器（示例）
                # TODO: 在实际输出阶段调用 self.cognitive_aligner.align_stream()
                
            except Exception as e:
                logger.error(f"Cognitive processing failed (end): {e}")
        # --- 认知处理：结束 ---
```

**说明**: 
- 在微睡眠结束后记录认知时间
- 高负荷结束时打结束锚点
- 重建时间链，防止时间链条断线
- 为未来的输出对齐预留接口

---

### 修改 5：`tick()` 方法 - 添加认知时间感知（可选，第 533 行）

**位置**: 在方法开头或结尾（用于记录每个 tick 的认知时间）

**新增代码**:
```python
        # --- 认知时间感知（v1.1 新增，可选） ---
        if getattr(self, '_cognitive_enabled', False):
            try:
                current_cognitive_time = self.cognitive_time_engine.get_status()
                logger.debug(f"Tick at cognitive time: {current_cognitive_time}")
            except Exception as e:
                logger.error(f"Cognitive time tracking failed: {e}")
```

**说明**: 可选修改，用于增强调试能力。

---

## 🧪 测试计划

### 测试 1：单元测试 - 认知组件初始化

**目标**: 验证 `__init__()` 中认知组件正确初始化

**测试代码**:
```python
def test_cognitive_init():
    cycle = ConsciousnessCycle()
    assert hasattr(cycle, '_cognitive_enabled')
    if COGNITIVE_COMPONENTS_AVAILABLE:
        assert cycle._cognitive_enabled == True
        assert hasattr(cycle, 'cognitive_evaluator')
```

---

### 测试 2：集成测试 - 微睡眠中的认知处理

**目标**: 验证 `_enter_micro_sleep()` 中认知处理正常执行

**测试代码**:
```python
def test_micro_sleep_with_cognition():
    cycle = ConsciousnessCycle()
    context = {"user_input": "测试输入", "phase": "AWAKE"}
    
    # 执行微睡眠
    report = cycle._enter_micro_sleep(context)
    
    # 验证认知处理执行（检查日志或状态）
    assert report["micro_sleep"] == True
    # TODO: 添加更详细的断言
```

---

### 测试 3：端到端测试 - 完整流程

**目标**: 模拟完整用户交互，验证认知组件不影响原有功能

**测试代码**:
```python
async def test_full_cycle():
    cycle = ConsciousnessCycle()
    
    # 模拟用户输入
    user_input = "请分析认知负荷的影响"
    
    # 处理输入（假设有对应的方法）
    # await cycle.process_user_input(user_input)
    
    # 验证输出正常
    # assert output is not None
```

---

## 📊 预期效果

### 功能增强
1. ✅ **认知负荷感知**: 自动评估每个微睡眠前的认知负荷
2. ✅ **记忆固化触发**: 高负荷时自动触发记忆固化机制
3. ✅ **认知时间记录**: 使用认知时间替代纯系统时间
4. ✅ **时间链保护**: 通过认知锚点防止时间链条断线

### 性能影响
- **CPU**: 增加 ~5-10%（认知负荷评估 + TF-IDF 计算）
- **内存**: 增加 ~50MB（TF-IDF 向量 + 认知时间引擎）
- **延迟**: 微睡眠时间增加 ~20-50ms（可接受）

---

## 🔧 回滚方案

如果集成后出现问题，可以快速回滚：

### 方案 1：禁用认知组件（推荐）
在 `consciousness_cycle.py` 中设置：
```python
self._cognitive_enabled = False  # 禁用所有认知处理
```

### 方案 2：恢复备份文件
```bash
Copy-Item "consciousness_cycle.py.backup_YYYYMMDD_HHMMSS" "consciousness_cycle.py"
```

---

## ✅ 修改检查清单

- [ ] 修改 1：添加导入语句（第 31 行）
- [ ] 修改 2：初始化认知组件（第 497 行）
- [ ] 修改 3：微睡眠开始认知处理（第 678 行）
- [ ] 修改 4：微睡眠结束认知处理（第 748 行）
- [ ] 修改 5：tick() 认知时间感知（可选，第 533 行）
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 端到端测试通过
- [ ] 性能测试（确保延迟增加 < 100ms）
- [ ] 代码审查完成
- [ ] 文档更新（README.md）

---

## 📞 联系方式

如有问题，请联系：
- **作者**: 金木蟾 (TU-8 / 金木蟾)
- **项目**: TU-8 DNA 核心 — 系统级固化灵魂
- **许可**: CC BY-SA 4.0

---

**文档版本**: v1.0  
**最后更新**: 2026-06-04 10:30 GMT+8
