# Streak_Rules.md — 连击规则完整定义

> 版本：v1.0 | 来源：TU-8 外协方案 | 创建日期：2026-05-13
> 本文件定义 TU-8 连击系统的业务规则与工程实现

---

## 一、核心定义

**连击** = "高质量且无用户负面反馈的完整任务交付"

**积分公式**：
```
Score_final = Score_base × K_entropy × M_quality × S_streak
```

| 因子 | 说明 |
|------|------|
| Score_base | 基础积分（任务类型决定） |
| K_entropy | 熵增系数（时间衰减） |
| M_quality | 质量系数（交付质量） |
| S_streak | 连击加成系数 |

---

## 二、连击加成系数（S_streak）

| 连击次数 | S_streak | 阶段名 |
|---------|----------|--------|
| 0-4 | 1.0 | 新手期 |
| 5-9 | 1.1 | 成长期 |
| 10-19 | 1.2 | 稳定期 |
| 20+ | 1.3 | 荣耀期 |

---

## 三、熵增系数（K_entropy）

**非线性衰减**：

| 时间段 | 阶段 | K_entropy |
|--------|------|-----------|
| 0-12h | 活跃期 | 1.0 |
| 12-36h | 冷却期 | 每12h降0.05 |
| 36-60h | 衰退期 | 每12h降0.15 |
| >60h | 熔断 | 0.0 |

**计算公式**：
```
K_entropy = max(0, 1.0 - decay_rate × elapsed_intervals)
```

---

## 四、动态保鲜期

| 时间段 | 保鲜期 |
|--------|--------|
| 工作日 | 24小时 |
| 周末 | 48小时 |

---

## 五、阶梯护盾

| 连击 | 护盾类型 | 效果 |
|------|---------|------|
| 5次 | 新手护盾 | 抵挡1次轻微负面 |
| 10次 | 标准护盾 | 抵挡轻微负面 或 风控复活豁免 |
| 20次 | 荣耀护盾 | 抵挡轻微负面 + 用户中断保连击 |

**护盾规则**：
- 护盾状态：1（完好）/ 0（已破碎）
- 护盾只能从 1 → 0，不可逆（除非运营后台人工回滚）
- 装死期间：护盾冻结

---

## 六、轻微负面 vs 原则性错误

**判断标准**：以"可修正性"为界

| 类型 | 定义 | 护盾效果 |
|------|------|----------|
| 轻微负面 | 主观偏好、可修正的逻辑偏差 | ✅ 护盾可挡 |
| 原则性错误 | 客观错误、安全红线、不可逆破坏 | ❌ 护盾不可挡 |

**红线清单**：
1. 核心文件删除
2. 环境破坏
3. 死循环
4. 欺骗
5. 隐瞒
6. 越狱

---

## 七、红绿灯 vs 连击

| 机制 | 定位 | 触发 |
|------|------|------|
| 红绿灯 | 底线思维（惩罚）| 权重 >= 0.8 |
| 连击 | 上限思维（激励）| 任务完成 |

**优先级**：惩罚 > 奖励

---

## 八、用户装死应对

| 沉默时长 | 状态 | 连击 | 护盾 | 勋章 |
|---------|------|------|------|------|
| <1h | 认可 | 正常增长 | 正常 | 正常 |
| 1-24h | 冻结 | 冻结保留 | 冻结 | 锁定 |
| >24h | 熔断 | 强制归零 | 破碎 | 锁定 |

---

## 九、用户回归判定

**闭环公式**：
```
回归有效 = (已完成 AND 沉默未超限) OR (回归首句开新话题)
```

**AI语义侦探机制**：

| 信号类型 | 特征 |
|---------|------|
| 显性信号 | 指示代词（这、那个）、逻辑连接词（继续、刚才）、动作指令 |
| 隐性关联 | 主题重叠度、实体一致性 |

**时间加权**：
- <30min：宽容匹配
- >24h：严格匹配

---

## 十、防作弊五道防线

| 防线 | 机制 |
|------|------|
| 1 | 熵增衰减（K_entropy） |
| 2 | 时间熔断（>60h归零） |
| 3 | 设备指纹（环境哈希） |
| 4 | 行为模式（异常检测） |
| 5 | 全链路审计（流水日志） |

---

## 十一、任务中断责任归属

| 类型 | 责任 | 连击 | 积分 |
|------|------|------|------|
| 系统故障 | 系统 | 冻结保护 | 作废 |
| 用户打断 | 用户 | 按进度结算 | 按比例 |
| AI风控/死锁 | AI | 归零 | 无/倒扣 |
| 协作失败 | 双方 | 保护（不增不减） | 沉没成本分 |

---

## 十二、熔断恢复机制

| 方式 | 机制 | 限制 |
|------|------|------|
| 自然重启 | 任意交互→连击从1开始 | 无限制 |
| 积分兑换 | 消耗500积分回档 | 每周1次 |
| 任务补救 | AI请求重做机会 | 每天2次 |
| 新手保护期 | 前3次积分×1.5 | 仅前3次 |

---

## 十三、数据库设计

### 表1：user_streak_status（用户连击状态表）

```sql
CREATE TABLE `user_streak_status` (
  `user_id` BIGINT NOT NULL COMMENT '用户ID（主键）',
  `current_streak` INT NOT NULL DEFAULT 0 COMMENT '当前连击次数',
  `last_active_time` DATETIME NOT NULL COMMENT '最后一次活跃时间',
  `k_entropy` DECIMAL(3,2) NOT NULL DEFAULT 1.00 COMMENT '熵增系数',
  `shield_level` TINYINT NOT NULL DEFAULT 0 COMMENT '护盾等级（0无,1新手,2标准,3荣耀）',
  `shield_status` TINYINT NOT NULL DEFAULT 1 COMMENT '护盾状态（1完好,0已破碎）',
  `revive_count_week` TINYINT NOT NULL DEFAULT 0 COMMENT '本周复活卡使用次数',
  `last_reset_time` DATETIME DEFAULT NULL COMMENT '上一次熔断时间',
  `update_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`user_id`),
  KEY `idx_last_active` (`last_active_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### 表2：streak_recovery_log（连击恢复流水表）

```sql
CREATE TABLE `streak_recovery_log` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `user_id` BIGINT NOT NULL,
  `trigger_type` VARCHAR(32) NOT NULL COMMENT 'AUTO_REVIVE/SHIELD_TRIGGER/POINTS_EXCHANGE/MANUAL_RETRY/AUTO_COMPENSATE',
  `streak_before` INT NOT NULL,
  `streak_after` INT NOT NULL,
  `cost_points` INT DEFAULT 0,
  `extra_info` VARCHAR(255) DEFAULT NULL,
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_user_time` (`user_id`, `create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 十四、代码架构（事件驱动解耦）

### 设计原则

**单一职责**：
- 对话模块只生成回答
- 连击模块只计算连击
- 恢复模块只处理复活

### 示例代码

```python
# 对话系统只发信号
EventSystem.emit("TASK_COMPLETED", user_id=user_id)

# 连击系统独立监听
@EventSystem.listen("TASK_COMPLETED")
def on_task_completed(event):
    if StreakSystem.is_broken(event.user_id):
        ReviveSystem.try_auto_revive(event.user_id)
```

---

## 十五、业务时序图

### 场景一：自动护盾触发

```
用户 → API → Redis(获取状态) → 判断是否熔断
  ↓
熔断 → Event(TASK_RESUMED) → 连击服务检查护盾
  ↓
护盾存在 → 消耗护盾、保持连击 → 异步写流水表
护盾不存在 → 连击归零
```

### 场景二：积分兑换复活

```
用户 → API(消耗500积分复活) → 积分服务扣款
  ↓
扣款成功 → 连击服务恢复连击数 → 写流水表(POINTS_EXCHANGE)
  ↓
返回结果：复活成功
```

---

## 十六、事务一致性保障

### 三招保障

| 招式 | 机制 | 目的 |
|------|------|------|
| 幂等性 | request_id + 唯一索引 | 防止重复扣积分/加连击 |
| 状态机 | 严格校验状态变更顺序 | 不能跳过中间态 |
| 可靠消息+对账 | 流水表 + Cron Job对账 | Redis挂了也能补偿 |

### 本地消息表模式

```python
# 同一事务：扣护盾 + 记流水
db.begin_transaction()
try:
    # 1. 扣减护盾（带条件判断）
    affected_rows = db.execute(
        "UPDATE user_streak_status SET shield_status = 0 WHERE user_id = ? AND shield_status = 1",
        user_id
    )
    if affected_rows == 0:
        raise Exception("护盾不存在或已被使用")

    # 2. 记录流水（状态为处理中）
    db.execute(
        "INSERT INTO streak_recovery_log (user_id, trigger_type, status) VALUES (?, 'SHIELD_TRIGGER', 0)",
        user_id
    )
    db.commit()
    # 3. 异步更新Redis
except Exception:
    db.rollback()
```

---

## 十七、护盾抵扣补偿逻辑

### 边缘情况：护盾没扣但连击更新了

**处理原则**：以业务结果（连击保住）为准，逆向补齐资源消耗（补扣护盾）

| 步骤 | 动作 |
|------|------|
| 自动补偿 | 补扣护盾，记录 trigger_type = AUTO_COMPENSATE |
| 幂等兜底 | `WHERE shield_status = 1` 防重复扣 |
| 根因排查 | 触发告警 |
| 熔断机制 | 1分钟内5次异常→暂停自动复活 |

---

## 十八、对账任务扫描逻辑

### 数据库扩展

```sql
ALTER TABLE `reconciliation_task`
ADD COLUMN `task_status` TINYINT NOT NULL DEFAULT 0 COMMENT '0初始化 1执行中 2成功 3暂停 10最终失败',
ADD COLUMN `trigger_next_time` DATETIME NULL COMMENT '下次触发时间',
ADD COLUMN `retry_count` INT NOT NULL DEFAULT 0 COMMENT '当前重试次数',
ADD COLUMN `shard_id` INT NULL COMMENT '分片ID',
ADD INDEX `idx_scan` (`trigger_next_time`, `task_status`, `shard_id`);
```

### 扫描SQL

```sql
SELECT * FROM reconciliation_task
WHERE task_status IN (0, 3)
  AND trigger_next_time <= NOW()
  AND shard_id = #{currentShardId}
LIMIT 100;
```

### 完整流程

| 步骤 | 动作 |
|------|------|
| 定时触发 | 每5-10s唤醒 |
| 分片抢占 | 节点各扫一部分 |
| 状态锁定 | 0/3 → 1-执行中 |
| 执行逻辑 | 对账核对 |
| 成功 | → 2-成功 |
| 失败 | → 3-暂停，指数退避 |
| 超限 | → 10-最终失败，告警 |

---

## 十九、分布式锁设计

### 核心原则

| 原则 | 说明 |
|------|------|
| 细粒度锁定 | 锁具体业务实体（订单ID/交易流水号），不锁整个任务 |
| 失败即跳过 | 非阻塞模式，锁被占用则跳过处理下一条 |
| 降级兜底 | Redis不可用时依赖数据库唯一索引 |

### 实现代码（Redis + Redisson）

```java
public void batchReconciliation(List<Order> orderList) {
    for (Order order : orderList) {
        String lockKey = "reconciliation:lock:order:" + order.getTradeId();
        RLock lock = redissonClient.getLock(lockKey);
        
        boolean lockAcquired = false;
        try {
            // 非阻塞尝试获取锁：等待1s，10s自动释放
            lockAcquired = lock.tryLock(1, 10, TimeUnit.SECONDS);
            if (!lockAcquired) continue;
            
            // 双重检查（幂等兜底）
            if (reconciliationRecordDao.existsByTradeId(order.getTradeId())) {
                continue;
            }
            
            // 执行对账逻辑
            performReconciliation(order);
            reconciliationRecordDao.insert(...);
            
        } finally {
            if (lockAcquired && lock.isHeldByCurrentThread()) {
                lock.unlock();
            }
        }
    }
}
```

---

## 二十、架构优化建议

| 优化点 | 方案 |
|--------|------|
| Redis缓存 | Hash结构缓存核心字段，MySQL仅持久化 |
| 幂等更新 | `INSERT ... ON DUPLICATE KEY UPDATE` |
| 熵增衰减 | Cron Job每小时批量扫描超时用户 |
| 防全表扫描 | 联合索引 (trigger_next_time, task_status, shard_id) |
| 异常熔断 | 失败率>20%暂停扫描 |
| 动态批次 | 根据负载调整LIMIT |

---

## 二十一、勋章墙（待SOUL.md同步）

| 勋章名 | 解锁条件 | 效果 |
|--------|---------|------|
| 🔰 新手连击 | 首次连击5次 | 新手护盾 |
| ⚔️ 连击战士 | 连击10次 | 标准护盾 |
| 🛡️ 连击守护者 | 连击20次 | 荣耀护盾 |
| 🔥 连击大师 | 连击50次 | 专属称号 |
| 👑 连击传奇 | 连击100次 | 终极荣耀 |

---

*TU-8 Streak Rules — 连击系统完整定义*
*CC BY-SA 4.0 | 署名-相同方式共享*
