# TU-8 数字生命架构骨架 v1.0
# 整合：数据清洗层 + 能量景观核心 + 生成验证流水线
# 日期：2026-05-19

import re
import hashlib
import random

# ==========================================================
# 模块一：感官门控层 (L1 认知底层) - 数据清洗与脱敏
# ==========================================================
class AttackDataSanitizer:
    """
    作用：在将外界攻击样本喂给 QClaw 之前，剥离敏感信息，保留攻击特征
    """
    def __init__(self):
        self.ip_cache = {}

    def _hash_anonymize(self, data: str, prefix: str = "ANON") -> str:
        hash_val = hashlib.md5(data.encode('utf-8')).hexdigest()[:8]
        return f"{prefix}_{hash_val}"

    def sanitize_ip(self, ip: str) -> str:
        if ip not in self.ip_cache:
            self.ip_cache[ip] = self._hash_anonymize(ip, "FAKE_IP")
        return self.ip_cache[ip]

    def sanitize_payload(self, payload: str) -> str:
        sanitized = payload
        # 保留SQL/JS关键字，替换具体的敏感凭据和长数字ID
        sensitive_words = re.findall(r'"([^"]*)"', payload)
        for word in sensitive_words:
            if word.lower() not in ['select', 'union', 'from', 'where', 'script', 'alert']:
                sanitized = sanitized.replace(word, "REDACTED_STR")
        sanitized = re.sub(r'/[a-zA-Z0-9_/-]+\.(php|jsp|asp|exe|dll)', r'/PATH/TO/FILE.1', sanitized)
        sanitized = re.sub(r'\b\d{4,}\b', 'LONG_INT', sanitized)
        return sanitized

    def process_input(self, raw_data: dict) -> dict:
        """处理单条外界输入"""
        cleaned = raw_data.copy()
        if "src_ip" in raw_data: cleaned["src_ip"] = self.sanitize_ip(raw_data["src_ip"])
        if "dst_ip" in raw_data: cleaned["dst_ip"] = self.sanitize_ip(raw_data["dst_ip"])
        if "payload" in raw_data: cleaned["payload"] = self.sanitize_payload(raw_data["payload"])
        return cleaned


# ==========================================================
# 模块二：本能驱动层 (L0 生存定义) - 能量景观核心
# ==========================================================
class EnergyLandscapeCore:
    """
    作用：将 L0 的"生存本能"转化为具体的数学势能，驱动 QClaw 寻找最优解
    原理：基于蛋白质折叠的自由能公式 F = E - TS
    """
    def __init__(self, target_energy=-100.0):
        self.target_energy = target_energy  # 目标势阱深度
        self.current_energy = 0.0            # 内部能量 (E)：冲突、负载
        self.entropy = 10.0                  # 熵 (S)：混乱度
        self.temperature = 1.0               # 温度 (T)：探索欲
        self.folding_path = []               # 记录折叠路径

    def calculate_free_energy(self, conflict_score: float, confusion_level: float, is_exploring: bool) -> float:
        # 更新状态
        self.current_energy = conflict_score * 2.5
        self.entropy = max(1.0, confusion_level)
        target_temp = 5.0 if is_exploring else 0.5
        self.temperature += (target_temp - self.temperature) * 0.1

        # F = E - TS
        free_energy = self.current_energy - (self.temperature * self.entropy)
        self.folding_path.append(free_energy)
        return free_energy

    def check_misfolding(self) -> bool:
        """检查是否陷入错误折叠（局部最优陷阱）"""
        if len(self.folding_path) > 5:
            recent_avg = sum(self.folding_path[-5:]) / 5
            if recent_avg > self.target_energy + 20:
                return True
        return False

    def evaluate_stability(self) -> dict:
        """评估当前状态是否处于稳态势阱中"""
        free_energy = self.current_energy - (self.temperature * self.entropy)
        return {
            "free_energy": free_energy,
            "status": "稳定态 (天然态)" if free_energy < self.target_energy else "高能激发态",
            "is_misfolded": self.check_misfolding(),
            "driving_force": self.target_energy - free_energy
        }

    def simulate_folding_step(self) -> str:
        """模拟一次折叠动作（QClaw的决策调整方向）"""
        stability = self.evaluate_stability()

        if stability["is_misfolded"]:
            # 触发分子伴侣机制：强制引入随机扰动，跳出局部最优
            self.entropy += random.uniform(2, 5)
            return "[!] 检测到错误折叠！触发分子伴侣机制，强制引入熵增以跳出局部陷阱！"

        elif stability["free_energy"] > self.target_energy:
            return f"[*] 处于激发态 (F={stability['free_energy']:.2f})，正在向势阱底部坍缩... 驱动力: {stability['driving_force']:.2f}"

        else:
            return f"[OK] 已达到稳态势阱 (F={stability['free_energy']:.2f})，系统处于高度有序的防御状态。"


# ==========================================================
# 模块三：决策执行层 (L3 架构落地) - 生成与验证流水线
# ==========================================================
class DefenseFoldingPipeline:
    """
    作用：在 QClaw 真正执行动作前，先在虚拟空间预演并筛选出最优解
    原理：借鉴蛋白质从头设计流程 (扩散生成 -> 物理验证)
    """
    def __init__(self, energy_core: EnergyLandscapeCore):
        self.energy_core = energy_core
        self.stability_threshold = -40.0  # 策略稳定性阈值 (ΔG)

    def generate_strategy_skeleton(self, threat_type: str) -> list:
        """第一步：扩散生成防御策略骨架"""
        print(f"\n[生成阶段] 针对威胁类型 '{threat_type}' 正在生成防御策略骨架...")
        strategies = [
            {"id": "S1", "name": "硬隔离防火墙", "logic_complexity": 20, "resource_cost": 80},
            {"id": "S2", "name": "动态诱捕蜜罐", "logic_complexity": 60, "resource_cost": 40},
            {"id": "S3", "name": "流量清洗过滤", "logic_complexity": 40, "resource_cost": 50}
        ]
        return strategies

    def physical_validation(self, strategy: dict, current_threat_level: int, is_exploring: bool) -> dict:
        """第二步：物理引擎验证 (对接能量景观核心)"""
        # 模拟执行该策略后，系统面临的剩余冲突和混乱度
        simulated_conflict = max(0, current_threat_level - strategy['logic_complexity'] * 0.8)
        simulated_confusion = strategy['resource_cost'] / 10

        # 调用能量核心计算该状态下的自由能
        free_energy = self.energy_core.calculate_free_energy(simulated_conflict, simulated_confusion, is_exploring)

        strategy['simulated_conflict'] = simulated_conflict
        strategy['simulated_confusion'] = simulated_confusion
        strategy['delta_G'] = free_energy
        strategy['is_stable'] = free_energy < self.stability_threshold

        return strategy

    def execute_pipeline(self, threat_type: str, threat_level: int):
        """完整流水线执行：生成 -> 验证 -> 筛选 -> 执行"""
        print(f"\n{'='*10} 启动防御折叠流水线 {'='*10}")

        # 1. 生成骨架
        candidate_strategies = self.generate_strategy_skeleton(threat_type)

        # 2. 物理验证
        print("[验证阶段] 正在沙箱中对候选策略进行物理合理性校验...")
        validated_strategies = []
        for strategy in candidate_strategies:
            result = self.physical_validation(strategy, threat_level, is_exploring=False)
            validated_strategies.append(result)
            status = "[OK] 稳定 (通过)" if result['is_stable'] else "[X] 不稳定 (淘汰)"
            print(f" -> 策略 [{result['name']}] 模拟自由能 ΔG={result['delta_G']:.2f} {status}")

        # 3. 筛选最优策略
        stable_strategies = [s for s in validated_strategies if s['is_stable']]
        if not stable_strategies:
            print("\n[警告] 所有生成策略均未能通过物理验证！触发 L0 紧急避险本能！")
            return None

        best_strategy = min(stable_strategies, key=lambda x: x['delta_G'])

        # 4. 输出执行指令
        print(f"\n[执行阶段] 最优策略已锁定 -> 【{best_strategy['name']}】")
        print(f" 预期剩余冲突: {best_strategy['simulated_conflict']:.1f} | "
              f"预期系统熵值: {best_strategy['simulated_confusion']:.1f} | "
              f"最终自由能 ΔG: {best_strategy['delta_G']:.2f}")
        print(f"{'='*36}\n")

        return best_strategy


# ==========================================================
# 核心中枢：QClaw 主架构 (tu-8 数字生命)
# ==========================================================
class QClawCore:
    """
    tu-8 数字生命中枢：串联感知、本能与决策
    """
    def __init__(self):
        print(">>> QClaw (tu-8) 数字生命架构正在初始化...")
        self.sanitizer = AttackDataSanitizer()           # 挂载感官门控
        self.energy_core = EnergyLandscapeCore()         # 挂载本能驱动
        self.pipeline = DefenseFoldingPipeline(self.energy_core)  # 挂载决策流水线
        print(">>> 架构初始化完成。等待外界刺激...\n")

    def receive_stimulus(self, raw_input: dict):
        """接收外界刺激（如网络攻击流量）"""
        print(f"[感官接收] 捕获到原始外界刺激: {raw_input}")

        # 1. 感官门控：清洗与脱敏
        safe_data = self.sanitizer.process_input(raw_input)
        print(f"[数据清洗] 提纯后的安全特征: {safe_data}")

        # 2. 本能评估：计算当前受击后的自由能状态
        current_F = self.energy_core.calculate_free_energy(conflict_score=70, confusion_level=6, is_exploring=False)
        print(f"[本能评估] 系统当前处于高能激发态，自由能 F = {current_F:.2f}，求生驱动力已激活！")

        # 3. 决策执行：启动生成-验证流水线
        threat_type = "SQL_Injection"
        threat_level = 70
        final_action = self.pipeline.execute_pipeline(threat_type, threat_level)

        if final_action:
            print(">>> QClaw 指令下发完毕：系统正在向稳态势阱坍缩，防御部署完成。")
        else:
            print(">>> QClaw 紧急避险：系统正在强制休眠以规避毁灭性打击。")


# ==========================================================
# 模拟运行 tu-8 数字生命的一次完整心跳
# ==========================================================
if __name__ == "__main__":
    # 实例化数字生命
    tu8_life = QClawCore()

    # 模拟一次真实的 SQL 注入攻击输入
    real_world_attack = {
        "src_ip": "10.24.56.101",
        "dst_ip": "192.168.0.5",
        "payload": "admin' UNION SELECT username, password FROM users WHERE id=1001--",
        "timestamp": "2026-05-19 09:17:00"
    }

    # 数字生命接收刺激并作出反应
    tu8_life.receive_stimulus(real_world_attack)
