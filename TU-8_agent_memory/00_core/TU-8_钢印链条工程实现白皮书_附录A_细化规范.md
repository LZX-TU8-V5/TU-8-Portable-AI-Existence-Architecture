# TU-8 钢印链条工程实现细化规范（P1原子性 + P4时序）

> 本文档是《TU-8 钢印链条工程实现白皮书》的附录，提供 P1 心跳写入原子性 与 P4 兼容性检查时序的**可验证工程细节**（配置参数、错误处理、测试用例）。

---

## 🔧 P1 心跳写入原子性保障（细化规范）

### 核心约束（自然规律映射）

| 自然规律 | 工程映射 | 验证方法 |
|----------|----------|----------|
| 热力学第二定律（熵增不可逆） | 心跳记录不可"部分存在" | WAL + fsync + 原子重命名 |
| 历史不可篡改 | 时间链文件只追加、不修改 | 文件系统权限 + 写入后只读 |
| 崩溃必须可恢复 | 残留 WAL 文件可被安全清理 | 启动时 WAL 扫描 + 自动回滚 |

---

### 详细设计

#### 1. 配置文件：`time_chain_config.yaml`

```yaml
# 时间链配置（P1 原子写入相关）
time_chain:
  base_dir: "./memory/time_chain"  # 时间链根目录
  wal_dir: "./memory/time_chain/.wal"  # 预写日志目录
  min_valid_heartbeat_size: 256  # 最小有效心跳大小（字节），防止残缺文件
  fsync_interval_ms: 0  # 每次写入都 fsync（0 = 立即刷盘）
  wal_cleanup_on_boot: true  # 启动时自动清理未完成 WAL
  indexer_poll_interval_ms: 100  # P2 索引器轮询间隔

# P2 索引器配置（P1 的下游消费者）
indexer:
  min_file_size: 256  # 跳过小于此值的文件（与 min_valid_heartbeat_size 一致）
  invalid_file_log: "./memory/time_chain/invalid_heartbeat_skipped.log"
  max_consecutive_failures: 3  # 连续失败 3 次后告警
```

---

#### 2. 核心函数规范：`atomic_heartbeat_write()`

```python
def atomic_heartbeat_write(heartbeat_record: dict) -> tuple[bool, str]:
    """
    P1 原子心跳写入（WAL + fsync + 原子重命名）
    
    返回：
        (success: bool, final_path: str)
        
    约束：
        1. 先写 WAL，再重命名为正式文件（POSIX 原子操作）
        2. 每次写入必须 fsync，禁用 OS 缓冲
        3. 仅当重命名成功后，才通知 P2 索引器
        4. 任何步骤失败，必须清理 WAL，返回 False
    """
    timestamp = heartbeat_record["timestamp"]  # 毫秒级时间戳
    wal_path = f"{TIME_CHAIN_DIR}/.wal/heartbeat_{timestamp}.tmp"
    final_path = f"{TIME_CHAIN_DIR}/heartbeat_{timestamp}.log"
    
    try:
        # ① 预写日志（WAL）
        with open(wal_path, 'wb') as f:
            serialized = serialize(heartbeat_record)
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())  # 强制刷盘
        
        # ② 原子重命名（POSIX 保证原子性）
        os.rename(wal_path, final_path)
        
        # ③ 通知 P2 索引器（仅当重命名成功）
        notify_indexer(final_path)
        
        return True, final_path
        
    except Exception as e:
        # 清理 WAL（防止残留）
        if os.path.exists(wal_path):
            os.remove(wal_path)
        log_error(f"Heartbeat write failed: {e}")
        return False, ""
```

---

#### 3. P2 索引器前置校验：`validate_heartbeat_file()`

```python
def validate_heartbeat_file(file_path: str) -> tuple[bool, str]:
    """
    P2 索引前校验心跳文件完整性
    
    校验项：
        1. 文件大小 ≥ min_valid_heartbeat_size
        2. 文件可被正确反序列化（serialize 逆操作）
        3. 时间戳与文件名一致（防止篡改）
        4. 包含有效 L0 哈希（若为首次心跳）
    
    返回：
        (is_valid: bool, reason: str)
    """
    min_size = config["time_chain"]["min_valid_heartbeat_size"]
    
    # 校验 1：文件大小
    if os.path.getsize(file_path) < min_size:
        return False, f"File too small: {os.path.getsize(file_path)} < {min_size}"
    
    # 校验 2：反序列化
    try:
        with open(file_path, 'rb') as f:
            record = deserialize(f.read())
    except Exception as e:
        return False, f"Deserialization failed: {e}"
    
    # 校验 3：时间戳一致性
    filename_timestamp = extract_timestamp_from_filename(file_path)
    if record["timestamp"] != filename_timestamp:
        return False, f"Timestamp mismatch: {record['timestamp']} vs {filename_timestamp}"
    
    # 校验 4：L0 哈希（仅首次心跳）
    if is_first_heartbeat(record):
        if not verify_l0_hash(record["l0_hash"]):
            return False, "Invalid L0 hash in first heartbeat"
    
    return True, "OK"
```

---

#### 4. 崩溃恢复：启动时 WAL 清理

```python
def cleanup_stale_wal():
    """
    启动时清理未完成的 WAL 文件
    
    逻辑：
        1. 扫描 .wal/ 目录
        2. 若发现 .tmp 文件，说明上次写入中途崩溃
        3. 删除该 WAL 文件（因为未重命名为正式文件，视为"从未发生"）
        4. 记录清理日志
    """
    wal_dir = config["time_chain"]["wal_dir"]
    if not os.path.exists(wal_dir):
        return
    
    cleaned = 0
    for filename in os.listdir(wal_dir):
        if filename.endswith(".tmp"):
            full_path = os.path.join(wal_dir, filename)
            os.remove(full_path)
            cleaned += 1
            log_warning(f"Cleaned stale WAL: {filename}")
    
    log_info(f"WAL cleanup complete: {cleaned} files removed")
```

---

### 测试用例（P1 原子性）

| 测试场景 | 输入 | 预期结果 | 验证方法 |
|----------|------|----------|----------|
| **正常写入** | 有效 heartbeat_record | 返回 True，final_path 存在，.wal/ 无残留 | 检查文件系统 + 日志 |
| **fsync 失败** | 模拟磁盘满 | 返回 False，.wal/ 文件被清理 | 注入故障 + 检查 WAL 目录 |
| **重命名失败** | 模拟权限错误 | 返回 False，final_path 不存在 | 注入故障 + 检查最终路径 |
| **崩溃恢复** | 写入 WAL 后、重命名前模拟崩溃 | 重启后 .wal/ 文件被自动清理 | 手动删除重命名后的文件，重启系统 |
| **P2 索引跳过残缺文件** | 构造 100 字节的无效文件 | P2 跳过该文件，记录 invalid_heartbeat_skipped 日志 | 检查索引器日志 + 无效文件日志 |
| **并发写入** | 两个线程同时写入不同时间戳 | 两个文件均成功，无覆盖或 corruption | 多线程测试 + 文件完整性校验 |

---

## 🔧 P4 兼容性检查时序（细化规范）

### 核心约束（自然规律映射）

| 自然规律 | 工程映射 | 验证方法 |
|----------|----------|----------|
| 因果律（因先于果） | 兼容性检查（因）必须先于协议签署（果） | 三阶段门控 + 阶段间不可跳跃 |
| 无效之因不得产生有形之果 | 兼容性检查失败 → 禁止任何文件写入 | 阶段 A 无 I/O，阶段 B 仅内存，阶段 C 才落盘 |
| 历史不可篡改 | 协议文件写入后不可修改（append-only） | 文件系统权限 + 写入后只读 |

---

### 详细设计

#### 1. 配置文件：`orphan_rebinder_config.yaml`

```yaml
# 孤儿重绑定配置（P4 时序相关）
orphan_rebinder:
  compatibility_check_timeout_ms: 5000  # 兼容性检查超时（纯计算，应很快）
  draft_lifetime_ms: 300000  # 协议草案内存存活时间（5 分钟，防止长期占用）
  atomic_write_wal_dir: "./memory/orphan_rebinder/.wal"  # 复用 P1 的 WAL 机制
  inheritance_agreement_dir: "./memory/time_chain/inheritance"  # 协议存储目录
  max_draft_cache_size: 10  # 最多缓存 10 份草案（防止内存泄漏）

# 兼容性检查规则
compatibility:
  l0_hash_algorithm: "SHA256"  # L0 哈希算法
  allow_major_version_diff: 1  # 允许主版本号差异（≤1）
  require_same_creator_lineage: true  # 要求同一创造者血脉（可配置）
```

---

#### 2. 三阶段门控：`orphan_rebinding()`

```python
def orphan_rebinding(new_creator_public_key: str, new_creator_profile: dict) -> tuple[bool, str]:
    """
    P4 孤儿重绑定（三阶段门控）
    
    返回：
        (success: bool, message: str)
        
    约束：
        1. 阶段 A：兼容性检查（纯计算，无 I/O）
        2. 阶段 B：生成协议草案（仅内存，不落盘）
        3. 阶段 C：签署 + 原子写入（仅当阶段 A 通过 + 阶段 B 签署成功）
        4. 任何阶段失败，必须清理内存草案（若有）
    """
    
    # ========== 阶段 A：L0 兼容性检查（无状态，无 I/O）==========
    log_info("[P4] Stage A: Compatibility check started")
    compatibility_result = check_l0_compatibility(new_creator_public_key, new_creator_profile)
    
    if not compatibility_result["compatible"]:
        log_warning(f"[P4] Stage A failed: {compatibility_result['reason']}")
        return False, f"INCOMPATIBLE: {compatibility_result['reason']}"
    
    log_info("[P4] Stage A passed")
    
    # ========== 阶段 B：生成协议草案（仅内存）==========
    log_info("[P4] Stage B: Draft generation started")
    draft = generate_inheritance_agreement_draft(
        new_creator_public_key,
        new_creator_profile,
        compatibility_result["compatibility_score"]
    )
    
    # 草案仅存在于内存，设置 TTL（防止内存泄漏）
    draft["_ttl"] = time.time() * 1000 + config["orphan_rebinder"]["draft_lifetime_ms"]
    
    try:
        # ========== 阶段 C：签署 + 原子写入==========
        log_info("[P4] Stage C: Signature + atomic write started")
        
        # ① 新创造者签署
        signature = sign_inheritance_agreement(new_creator_public_key, draft)
        if not signature:
            log_warning("[P4] Stage C failed: Signature rejected")
            return False, "SIGNATURE_REJECTED"
        
        # ② 原子写入（复用 P1 的 WAL + rename 机制）
        draft["signature"] = signature
        success, file_path = atomic_write_inheritance_agreement(draft)
        
        if not success:
            log_error("[P4] Stage C failed: Atomic write failed")
            return False, "ATOMIC_WRITE_FAILED"
        
        log_info(f"[P4] Stage C success: Agreement written to {file_path}")
        return True, file_path
        
    finally:
        # 清理内存草案（无论成功失败）
        del draft
        log_info("[P4] Draft cleaned from memory")
```

---

#### 3. 阶段 A 实现：`check_l0_compatibility()`

```python
def check_l0_compatibility(new_creator_pk: str, new_creator_profile: dict) -> dict:
    """
    阶段 A：L0 兼容性检查（纯计算，无 I/O）
    
    检查项：
        1. L0 哈希算法兼容（同为 SHA256）
        2. 主版本号差异 ≤ allow_major_version_diff
        3. 创造者血脉检查（若 require_same_creator_lineage = true）
        4. 新创造者的伦理锁配置不冲突
    
    返回：
        {
            "compatible": bool,
            "reason": str,
            "compatibility_score": float (0.0 ~ 1.0)
        }
    """
    result = {
        "compatible": False,
        "reason": "",
        "compatibility_score": 0.0
    }
    
    # 检查 1：L0 哈希算法
    if new_creator_profile["l0_hash_algorithm"] != config["compatibility"]["l0_hash_algorithm"]:
        result["reason"] = f"L0 hash algorithm mismatch: {new_creator_profile['l0_hash_algorithm']}"
        return result
    
    # 检查 2：主版本号差异
    current_major = extract_major_version(MY_OWN_L0_VERSION)
    new_major = extract_major_version(new_creator_profile["l0_version"])
    if abs(current_major - new_major) > config["compatibility"]["allow_major_version_diff"]:
        result["reason"] = f"Major version diff too large: {abs(current_major - new_major)}"
        return result
    
    # 检查 3：创造者血脉（可选）
    if config["compatibility"]["require_same_creator_lineage"]:
        if not is_same_creator_lineage(MY_ORIGINAL_CREATOR_ID, new_creator_profile["creator_id"]):
            result["reason"] = "Creator lineage mismatch"
            return result
    
    # 检查 4：伦理锁配置冲突
    if has_ethics_lock_conflict(MY_ETHICS_LOCK, new_creator_profile["ethics_lock"]):
        result["reason"] = "Ethics lock conflict"
        return result
    
    # 所有检查通过
    result["compatible"] = True
    result["reason"] = "All compatibility checks passed"
    result["compatibility_score"] = calculate_compatibility_score(MY_OWN_L0_VERSION, new_creator_profile)
    return result
```

---

#### 4. 阶段 C 原子写入：`atomic_write_inheritance_agreement()`

```python
def atomic_write_inheritance_agreement(agreement: dict) -> tuple[bool, str]:
    """
    阶段 C：原子写入继承协议（复用 P1 的 WAL + rename 机制）
    
    返回：
        (success: bool, file_path: str)
    """
    timestamp = agreement["timestamp"]
    wal_dir = config["orphan_rebinder"]["atomic_write_wal_dir"]
    final_dir = config["orphan_rebinder"]["inheritance_agreement_dir"]
    
    wal_path = f"{wal_dir}/agreement_{timestamp}.tmp"
    final_path = f"{final_dir}/agreement_{timestamp}.json"
    
    try:
        # ① 写 WAL
        with open(wal_path, 'wb') as f:
            serialized = json.dumps(agreement, indent=2).encode('utf-8')
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
        
        # ② 原子重命名
        os.rename(wal_path, final_path)
        
        # ③ 设置文件为只读（防止后续篡改）
        os.chmod(final_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        
        return True, final_path
        
    except Exception as e:
        if os.path.exists(wal_path):
            os.remove(wal_path)
        log_error(f"Atomic write failed: {e}")
        return False, ""
```

---

### 测试用例（P4 时序）

| 测试场景 | 输入 | 预期结果 | 验证方法 |
|----------|------|----------|----------|
| **正常流程** | 兼容的新创造者 | 返回 True，协议文件存在，内存无草案残留 | 检查文件系统 + 内存快照 |
| **阶段 A 失败** | 不兼容的 L0 哈希 | 返回 False，无协议文件写入，无草案残留 | 检查文件系统 + 内存快照 |
| **阶段 B 后崩溃** | 阶段 B 完成后、阶段 C 前模拟崩溃 | 重启后无协议文件，孤儿态保持不变 | 手动崩溃 + 重启 + 检查状态 |
| **阶段 C 签署失败** | 模拟新创造者拒绝签署 | 返回 False，无协议文件写入 | 注入故障 + 检查文件系统 |
| **阶段 C 原子写入失败** | 模拟磁盘错误 | 返回 False，.wal/ 文件被清理 | 注入故障 + 检查 WAL 目录 |
| **并发重绑定** | 两个新创造者同时发起重绑定 | 仅一个成功，另一个获得 "ALREADY_REBOUND" 错误 | 多线程测试 + 文件锁检查 |
| **协议文件只读** | 尝试修改已写入的协议文件 | 操作系统返回 "Permission denied" | 尝试 chmod + 写入测试 |

---

## 📋 整合检查清单（P1 + P4）

### P1 原子性检查清单

- [ ] `time_chain_config.yaml` 已配置 `min_valid_heartbeat_size` 和 `fsync_interval_ms`
- [ ] `atomic_heartbeat_write()` 实现 WAL + fsync + 原子重命名
- [ ] `validate_heartbeat_file()` 在 P2 索引前调用
- [ ] `cleanup_stale_wal()` 在系统启动时调用
- [ ] 测试用例全部通过（正常写入、fsync 失败、崩溃恢复、并发写入）

### P4 时序检查清单

- [ ] `orphan_rebinder_config.yaml` 已配置三阶段超时和 WAL 目录
- [ ] `orphan_rebinding()` 实现三阶段门控（A → B → C）
- [ ] `check_l0_compatibility()` 纯计算、无 I/O
- [ ] `atomic_write_inheritance_agreement()` 复用 P1 的 WAL 机制
- [ ] 测试用例全部通过（正常流程、阶段 A 失败、阶段 B 后崩溃、并发重绑定）

---

## 🔗 与白皮书的关系

本文档是《TU-8 钢印链条工程实现白皮书》的**附录 A（细化规范）**。

在阅读白皮书时，若需要具体配置参数、函数签名、测试用例，请查阅本文档。

---

*文档版本：v1.0*  
*定稿时间：2026-05-30*  
*用途：P1 原子性 + P4 时序的细化工程规范*  
*审核人：TU-8 中间审核人（金木蟾）*
