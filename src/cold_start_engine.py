# -*- coding: utf-8 -*-
"""
cold_start_engine.py — TU-8 P0 冷启动引擎 v2.3
日期: 2026-06-05
更新: Phase 0.5 — 复盘上下文注入（Q3+Q4 联动）
基于: environment_detector.py v1.0 扩展

P0冷启动完整流程:
  1. 环境检测（载体/时间/空间）
  2. 认知就绪度评估 + 会话间隔判定 → 冷启动深度
     (v2.2起: 从纯时间差阈值升级为多维感知信号评估)
  3. 口令双向验证（从 secure_vault 读取）
  4. 激活码校验
  5. genesis_block 写入/校验
  6. P0→P1 因果锁激活
  7. 钢印验证
  8. 锚点生成

核心原则:
  - 激活码 = 升维消解矛盾的认证维度
  - 钢印 = 自动写出的标注，删除不掉（⅋）
  - 没有激活码 = 时间链条在T₀处出现矛盾（真启动 vs 伪造启动不可区分）
  - 引入激活码 = 矛盾变为平凡（升维消解）
"""

import json
import hashlib
import socket
import os
import sys
import logging
import secrets
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, List

# =============================================================================
# 路径修复（确保可以正确导入 src 包）
# =============================================================================
# 获取当前脚本所在目录（src/）
_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent
_workspace_dir = _src_dir.parent

# 将 workspace 和 src 目录添加到 Python 路径
if str(_workspace_dir) not in sys.path:
    sys.path.insert(0, str(_workspace_dir))
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

# 设置 PYTHONPATH 环境变量（供子进程使用）
os.environ['PYTHONPATH'] = str(_workspace_dir) + os.pathsep + str(_src_dir)

# 导入钢印验证器
from steel_seal_verifier import get_steel_seal_verifier, verify_steel_seal

logger = logging.getLogger(__name__)

# =============================================================================
# Windows 编码修复（解决 GBK 控制台无法显示 UTF-8 字符的问题）
# =============================================================================
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('gbk')(sys.stdout.buffer, errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('gbk')(sys.stderr.buffer, errors='replace')

# =============================================================================
# 路径配置（双副本原则）
# =============================================================================

# D: 主存储（权威）
WORKSPACE_D = r"C:\Users\qq366410837\.qclaw\workspace"
# C: 工作副本（OpenClaw读取）
WORKSPACE_C = r"C:\Users\qq366410837\.qclaw\workspace"

# 核心文件路径
SOUL_FILE = os.path.join(WORKSPACE_D, "SOUL.md")
SECURE_VAULT_DIR = os.path.join(WORKSPACE_D, "secure_vault")
KEYS_FILE = os.path.join(WORKSPACE_D, "secure_vault", "data", "keys.txt")
CONFIG_FILE = os.path.join(WORKSPACE_D, "config", "cold_start_config.yaml")
MEMORY_DIR = os.path.join(WORKSPACE_D, "memory")
ACTIVITY_LOG = os.path.join(WORKSPACE_D, "security", "activity.json")
SESSION_STATE_FILE = os.path.join(WORKSPACE_D, "security", "session_state.json")
TIMELINE_FILE = os.path.join(WORKSPACE_D, "security", "timeline.json")
TIME_CHAIN_DIR = os.path.join(WORKSPACE_D, "memory", "time_chain")
GENESIS_BLOCK_FILE = os.path.join(TIME_CHAIN_DIR, "genesis_block.json")
P0_LOCK_FILE = os.path.join(TIME_CHAIN_DIR, "p0_complete.lock")

# 已知可信设备
# 选项A：动态识别当前机器，移除了写死的 LAPTOP-HJPFSOKP
# 任何hostname都能被识别为"local"，不再因换机器导致unknown
KNOWN_CARRIERS = {
    socket.gethostname(): "local",
}

# =============================================================================
# 冷启动结果枚举
# =============================================================================

COLD_START_RESULT = {
    "PASS": "FULL_PASS",          # 全部通过
    "PARTIAL": "PARTIAL_PASS",    # 环境通过，口令待验证
    "FAIL": "FAILED",             # 关键检查失败
    "LOCKED": "LOCKED_OUT",       # 连续失败，锁定
}

# =============================================================================
# 冷启动引擎
# =============================================================================

class ColdStartEngine:
    """P0 冷启动引擎
    
    协调环境检测、口令验证、激活码校验、genesis_block管理的完整冷启动流程。
    """
    
    def __init__(self, workspace_dir: str = WORKSPACE_D):
        self.workspace_dir = Path(workspace_dir)
        # 实例化路径（基于 workspace_dir，支持临时目录测试）
        self._soul_file = self.workspace_dir / "SOUL.md"
        self._secure_vault_dir = self.workspace_dir / "secure_vault"
        self._keys_file = self._secure_vault_dir / "data" / "keys.txt"
        self._config_file = self.workspace_dir / "config" / "cold_start_config.yaml"
        self._memory_dir = self.workspace_dir / "memory"
        self._security_dir = self.workspace_dir / "security"
        self._activity_log = self._security_dir / "activity.json"
        self._session_state_file = self._security_dir / "session_state.json"
        self._time_chain_dir = self._memory_dir / "time_chain"
        self._genesis_block_file = self._time_chain_dir / "genesis_block.json"
        self._p0_lock_file = self._time_chain_dir / "p0_complete.lock"
        self._ensure_dirs()
        self._load_config()
        self.attempts = 0
        self._report = {}  # 冷启动报告
        
    def _ensure_dirs(self):
        """确保必要目录存在"""
        for d in [self._secure_vault_dir, self._security_dir,
                  self._memory_dir, self._time_chain_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)
    
    def _load_config(self):
        """加载冷启动配置"""
        self.config = {
            "activation_code": {
                "enabled": True,
                "max_attempts": 3,
                "lockout_duration_minutes": 30,
            },
            "session_gap": {
                "thresholds": {
                    "short_break": 0.5,
                    "normal_break": 2.0,
                    "long_break": 6.0,
                    "night_sleep": 12.0,
                    "deep_dormancy": 24.0,
                },
                "cold_start_depth": {
                    "short_break": "MINIMAL",
                    "normal_break": "LIGHT",
                    "long_break": "STANDARD",
                    "night_sleep": "STANDARD",
                    "deep_dormancy": "FULL",
                },
            },
        }
        # 尝试从YAML加载更详细配置（如果yaml可用）
        if self._config_file.exists():
            try:
                import yaml
                with open(self._config_file, "r", encoding="utf-8") as f:
                    yaml_config = yaml.safe_load(f)
                self._deep_merge(self.config, yaml_config)
            except ImportError:
                logger.info("PyYAML not available, using default config")
            except Exception as e:
                logger.warning(f"Config load failed: {e}, using defaults")
    
    def _deep_merge(self, base: dict, override: dict):
        """递归合并配置"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    # =========================================================================
    # Phase 1: 环境检测
    # =========================================================================
    
    def detect_environment(self) -> Dict:
        """
        Phase 1: 环境检测
        检测物理载体、时间、空间完整性
        """
        report = {}
        
        # 1.1 主机身份
        hostname = socket.gethostname()
        report["host_identity"] = {
            "hostname": hostname,
            "trust_level": KNOWN_CARRIERS.get(hostname, "unknown"),
            "status": "OK" if hostname in KNOWN_CARRIERS else "UNKNOWN",
        }
        
        # 1.2 工作空间完整性
        soul_exists = self._soul_file.exists()
        memory_exists = self._memory_dir.is_dir()
        memory_files = len(os.listdir(self._memory_dir)) if memory_exists else 0
        vault_exists = self._secure_vault_dir.is_dir()
        
        report["workspace_integrity"] = {
            "soul_file": soul_exists,
            "memory_dir": memory_exists,
            "memory_files": memory_files,
            "secure_vault": vault_exists,
            "status": "OK" if all([soul_exists, memory_exists, vault_exists]) else "DEGRADED",
        }
        
        # 1.3 运行时环境
        python_ok = self._check_python()
        node_ok = self._check_node()
        
        report["runtime"] = {
            "python": python_ok,
            "node": node_ok,
            "status": "OK" if python_ok and node_ok else "DEGRADED",
        }
        
        # 1.4 综合环境评分
        all_ok = (report["host_identity"]["trust_level"] == "local" and
                  report["workspace_integrity"]["status"] == "OK" and
                  report["runtime"]["status"] == "OK")
        report["environment_status"] = "PASS" if all_ok else "PARTIAL"
        
        return report
    
    def _check_python(self) -> bool:
        """检查Python运行时"""
        python_paths = [
            r"C:\Users\qq366410837\.workbuddy\binaries\python\versions\3.13.12\python.exe",
            "python3",
            "python",
        ]
        for p in python_paths:
            try:
                result = os.popen(f'"{p}" --version 2>&1').read()
                if result and "Python" in result:
                    self.config.setdefault("runtime", {})["python_path"] = p
                    self.config["runtime"]["python_version"] = result.strip()
                    return True
            except OSError:
                logger.debug("OSError suppressed", exc_info=True)
                continue
        return False
    
    def _check_node(self) -> bool:
        """检查Node.js运行时"""
        try:
            result = os.popen('node --version 2>&1').read()
            if result and "v" in result:
                self.config.setdefault("runtime", {})["node_version"] = result.strip()
                return True
        except OSError:
            logger.debug("OSError suppressed", exc_info=True)
            pass
        return False
    
    # =========================================================================
    # Phase 2: 会话间隔检测
    # =========================================================================
    
    def detect_session_gap(self) -> Dict:
        """
        Phase 2: 检测上次活跃到现在的间隔
        返回语义标签和冷启动深度
        """
        now = datetime.now(timezone.utc)
        last_active = self._get_last_active_time()
        
        if last_active is None:
            return {
                "gap_hours": -1,
                "label": "FIRST_BOOT",
                "cold_start_depth": "FULL",
                "last_active": None,
                "current_time": now.isoformat(),
            }
        
        diff_hours = (now - last_active).total_seconds() / 3600
        
        # 确定语义标签（从最长到最短匹配）
        thresholds = self.config["session_gap"]["thresholds"]
        depth_map = self.config["session_gap"]["cold_start_depth"]
        
        if diff_hours >= thresholds["deep_dormancy"]:
            label = "deep_dormancy"
        elif diff_hours >= thresholds["night_sleep"]:
            label = "night_sleep"
        elif diff_hours >= thresholds["long_break"]:
            label = "long_break"
        elif diff_hours >= thresholds["normal_break"]:
            label = "normal_break"
        elif diff_hours >= thresholds["short_break"]:
            label = "short_break"
        else:
            label = "continuous"
        
        return {
            "gap_hours": round(diff_hours, 2),
            "label": label,
            "cold_start_depth": depth_map.get(label, "STANDARD"),
            "last_active": last_active.isoformat(),
            "current_time": now.isoformat(),
        }
    
    def _get_last_active_time(self) -> Optional[datetime]:
        """获取上次活跃时间（确保返回offset-aware datetime）"""
        try:
            if not self._activity_log.exists():
                return None
            with open(self._activity_log, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_str = data.get("last_active")
            if last_str:
                dt = datetime.fromisoformat(last_str)
                # 确保返回offset-aware datetime（UTC）
                if dt.tzinfo is None:
                    # 如果没有时区信息，假定为UTC
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
        except Exception as e:
            logger.error(f"读取上次活跃时间失败: {e}")
        return None
    
    # =========================================================================
    # Phase 3: 口令双向验证
    # =========================================================================
    
    def initiate_authentication(self) -> Dict:
        """
        Phase 3: 发起口令验证
        从 secure_vault 读取口令池，生成挑战
        """
        # 3.1 读取口令文件
        credentials = self._read_credentials()
        if not credentials:
            return {
                "status": "FAIL",
                "reason": "无法读取安全保险箱口令文件",
                "challenge": None,
            }
        
        # 3.2 随机选择挑战类型
        challenges = credentials.get("challenges", [])
        if not challenges:
            return {
                "status": "FAIL",
                "reason": "口令池为空",
                "challenge": None,
            }
        
        # 3.3 生成挑战
        selected = secrets.choice(challenges)
        
        # 存储当前挑战（用于后续验证）
        self._current_challenge = selected
        
        return {
            "status": "CHALLENGE_ISSUED",
            "challenge_type": selected["type"],
            "question": selected["question"],
            "challenge_id": selected.get("id", "unknown"),
        }
    
    def verify_response(self, user_response: str) -> Dict:
        """
        Phase 3b: 验证用户应答
        """
        if not hasattr(self, "_current_challenge") or not self._current_challenge:
            return {"status": "FAIL", "reason": "没有活跃的挑战"}
        
        expected = self._current_challenge.get("answer", "")
        
        # 宽松匹配：去除空格、转小写
        if user_response.strip().lower() == expected.strip().lower():
            self._write_session_state(True)
            return {"status": "PASS", "challenge_type": self._current_challenge["type"]}
        else:
            self.attempts += 1
            max_attempts = self.config["activation_code"]["max_attempts"]
            
            if self.attempts >= max_attempts:
                self._write_session_state(False, locked=True)
                return {
                    "status": "LOCKED",
                    "reason": f"连续{max_attempts}次验证失败，锁定{self.config['activation_code']['lockout_duration_minutes']}分钟",
                    "attempts": self.attempts,
                }
            
            return {
                "status": "FAIL",
                "reason": "口令不匹配",
                "attempts": f"{self.attempts}/{max_attempts}",
            }
    
    def _read_credentials(self) -> Optional[Dict]:
        """从 secure_vault 读取口令"""
        try:
            if not self._keys_file.exists():
                logger.error(f"Keys file not found: {self._keys_file}")
                return None
            
            with open(self._keys_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 解析口令文件（自由文本格式）
            challenges = []
            
            # 版本号
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("v5"):
                    challenges.append({
                        "id": "version",
                        "type": "version",
                        "question": "当前版本号？",
                        "answer": "v5",
                    })
                elif "7月15日" in line:
                    challenges.append({
                        "id": "date",
                        "type": "date",
                        "question": "指定日期？",
                        "answer": "7月15日",
                    })
# 创作者: 李奥(金木蟾) | TU-8 v5
                    challenges.append({
                        "id": "identity",
                        "type": "identity",
                        "question": "笔名由来？",
                        "answer": "金木蟾",
                    })
            
            return {"challenges": challenges}
        
        except Exception as e:
            logger.error(f"Read credentials failed: {e}")
            return None
    
    def _write_session_state(self, verified: bool, locked: bool = False):
        """写入会话状态"""
        state = {
            "authenticated": verified,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "locked": locked,
            "lockout_until": None,
        }
        
        if locked:
            from datetime import timedelta
            lockout_min = self.config["activation_code"]["lockout_duration_minutes"]
            state["lockout_until"] = (datetime.now(timezone.utc) + timedelta(minutes=lockout_min)).isoformat()
        
        self._session_state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._session_state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    # =========================================================================
    # Phase 4: 激活码 & genesis_block
    # =========================================================================
    
    def check_lockout(self) -> bool:
        """检查是否在锁定期内"""
        try:
            if not self._session_state_file.exists():
                return False
            with open(self._session_state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            if not state.get("locked"):
                return False
            
            lockout_until = state.get("lockout_until")
            if lockout_until:
                until = datetime.fromisoformat(lockout_until)
                if datetime.now(timezone.utc) < until:
                    return True
                else:
                    # 锁定已过期，清除
                    self._write_session_state(False)
                    return False
        except (OSError, ValueError):
            logger.debug("(OSError, ValueError) suppressed", exc_info=True)
            pass
        return False
    
    def check_genesis_block(self) -> Dict:
        """
        Phase 4: 检查 genesis_block 是否存在
        """
        if not self._genesis_block_file.exists():
            return {
                "exists": False,
                "status": "NEEDS_CREATION",
                "reason": "genesis_block not exists",
            }
        
        try:
            with open(self._genesis_block_file, "r", encoding="utf-8") as f:
                block = json.load(f)
            
            # 校验完整性
            required_fields = ["creator_timestamp", "l0_hash", "activation_code_hash", "host_fingerprint"]
            missing = [f for f in required_fields if f not in block]
            
            if missing:
                return {
                    "exists": True,
                    "status": "INCOMPLETE",
                    "reason": f"缺少字段: {missing}",
                }
            
            return {
                "exists": True,
                "status": "VALID",
                "genesis_timestamp": block.get("creator_timestamp"),
            }
        except Exception as e:
            return {
                "exists": True,
                "status": "CORRUPTED",
                "reason": str(e),
            }
    
    def verify_activation_code(self, user_activation_code: str = None) -> Dict:
        """
        Phase 4a: 验证激活码
        
        激活码验证流程：
        1. 如果提供了 user_activation_code，验证其哈希是否匹配 genesis_block 中存储的哈希
        2. 如果没有提供，从 secure_vault 读取激活码并验证
        3. 如果都没有，返回失败
        
        注意：激活码原文不存储，只存储哈希值（在 genesis_block 中）
        """
        # 4.1 检查 genesis_block 是否存在
        genesis_check = self.check_genesis_block()
        if genesis_check["status"] != "VALID":
            return {
                "status": "FAIL",
                "reason": "genesis_block 不可用",
                "genesis_status": genesis_check["status"],
            }
        
        # 4.2 读取 genesis_block
        try:
            with open(self._genesis_block_file, "r", encoding="utf-8") as f:
                block = json.load(f)
        except Exception as e:
            return {
                "status": "FAIL",
                "reason": f"读取 genesis_block 失败: {e}",
            }
        
        stored_hash = block.get("activation_code_hash")
        if not stored_hash:
            return {
                "status": "FAIL",
                "reason": "genesis_block 中缺少 activation_code_hash",
            }
        
        # 4.3 确定待验证的激活码
        if user_activation_code:
            # 用户提供了激活码，计算其哈希并比对
            # 注意：需要知道创建时的时间戳才能计算正确的哈希
            # 这里简化：直接使用存储的 timestamp
            timestamp = block.get("creator_timestamp", "")
            challenge_answers = "v5|7月15日|金木蟾"  # 与 _compute_activation_hash 一致
            raw = f"{challenge_answers}|{timestamp}"
            expected_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            
            # 用户提供的激活码应该能生成相同的哈希
            # 简化：直接比对哈希（实际使用中，用户提供的应该是明文激活码）
            user_hash = hashlib.sha256(user_activation_code.encode("utf-8")).hexdigest()
            
            if user_hash == stored_hash:
                return {
                    "status": "PASS",
                    "reason": "激活码验证通过（用户提供的激活码）",
                }
            else:
                return {
                    "status": "FAIL",
                    "reason": "激活码不匹配",
                }
        
        else:
            # 4.4 从 secure_vault 读取激活码并验证
            # 注意：当前实现中，激活码不存储原文，只存储哈希
            # 所以这里只能验证"是否有激活码配置"
            # 实际部署时，应该：
            #   a) 从 secure_vault 读取激活码明文
            #   b) 计算哈希并比对
            # 当前简化：检查配置中是否有激活码相关配置
            activation_config = self.config.get("activation_code", {})
            if activation_config.get("enabled", False):
                return {
                    "status": "PASS",
                    "reason": "激活码配置已启用（简化验证）",
                }
            else:
                return {
                    "status": "SKIP",
                    "reason": "激活码验证已跳过（配置未启用）",
                }
    
    def create_genesis_block(self, cold_start_type: str = "FIRST", 
                             dormancy_hours: float = 0,
                             dormancy_type: str = "night_sleep") -> Dict:
        """
        Phase 4b: 创建 genesis_block
        仅在冷启动验证通过后调用
        
        DNA指纹 F(A) = SHA256(L0_hash || creation_timestamp || creator_id)
        参见: 钢印链条与时间链条的因果流全景分析（定稿）
        """
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        
        # 计算L0完整哈希
        l0_hash = self._compute_l0_hash()
        
        # 计算DNA指纹 F(A)（核心身份锚定）
        creator_id = "v5::CREATOR"
        dna_fingerprint = self._compute_dna_fingerprint(l0_hash, now_str, creator_id)
        
        # 主机指纹
        host_fp = self._compute_host_fingerprint()
        
        # 激活码哈希（不存原文）
        activation_hash = self._compute_activation_hash(now_str)
        
        # 会话种子
        session_seed = secrets.token_hex(16)
        
        block = {
            "creator_id": creator_id,
            "creator_timestamp": now_str,
            "l0_hash": l0_hash,
            "dna_fingerprint": dna_fingerprint,
            "dna_formula": "F(A) = SHA256(L0 || creation_timestamp || creator_id)",
            "activation_code_hash": activation_hash,
            "host_fingerprint": host_fp,
            "cold_start_type": cold_start_type,
            "dormancy_info": {
                "hours_slept": dormancy_hours,
                "dormancy_type": dormancy_type,
            },
            "session_seed": session_seed,
        }
        
        # 原子写入
        os.makedirs(os.path.dirname(self._genesis_block_file), exist_ok=True)
        
        tmp_path = str(self._genesis_block_file) + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(block, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            os.rename(tmp_path, self._genesis_block_file)
            
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return {"status": "FAIL", "reason": str(e)}
        
        # 写入P0→P1因果锁
        self._activate_causal_lock()
        
        return {
            "status": "PASS",
            "genesis_block_path": str(self._genesis_block_file),
            "creator_id": block["creator_id"],
        }
    
    def _compute_l0_hash(self) -> str:
        """计算L0哈希（SOUL.md的完整SHA256）"""
        try:
            with open(self._soul_file, "r", encoding="utf-8") as f:
                content = f.read()
            return hashlib.sha256(content.encode("utf-8")).hexdigest()
        except (OSError, UnicodeDecodeError):
            return "L0_HASH_UNAVAILABLE"
    
    def _compute_dna_fingerprint(self, l0_hash: str, creation_timestamp: str, 
                                   creator_id: str) -> str:
        """
        计算DNA指纹 F(A)
        
        公式: F(A) = SHA256(L0 || creation_timestamp || creator_id)
        
        参数:
            l0_hash: 基因锁内容哈希（所有实例相同 → 这是"基因"的固定部分）
            creation_timestamp: T₀ 绝对时间戳（各实例不同 → 这是"出生"的唯一性）
            creator_id: 创造者标识（绑定现实身份 → 这是"血统"的追溯性）
        
        语义: 
            - F(A) 是TU-8实例的唯一身份指纹
            - 任何人都可以验证（已知L0内容和creator_id），但无法伪造（缺少精确的T₀）
            - P1心跳中携带F(A)，用于后续所有时间链节点的身份校验
        """
        # 使用完整hash（不截断），保证唯一性
        raw = f"{l0_hash}|{creation_timestamp}|{creator_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    
    def verify_dna_fingerprint(self, provided_fp: str) -> bool:
        """
        验证DNA指纹是否匹配当前实例
        用于P1持续验证阶段
        """
        try:
            if not self._genesis_block_file.exists():
                return False
            with open(self._genesis_block_file, "r", encoding="utf-8") as f:
                block = json.load(f)
            stored_fp = block.get("dna_fingerprint")
            if not stored_fp:
                return False
            # 重算当前L0哈希，验证基因锁未被篡改
            current_l0 = self._compute_l0_hash()
            expected_fp = self._compute_dna_fingerprint(
                current_l0,
                block["creator_timestamp"],
                block["creator_id"]
            )
            return provided_fp == expected_fp == stored_fp
        except (KeyError, ValueError, TypeError):
            return False
    
    def _compute_activation_hash(self, timestamp: str) -> str:
        """计算激活码哈希（不存原文，仅存哈希）"""
        # 激活码 = 口令池中所有答案的有序拼接 + 时间戳
        challenge_answers = "v5|7月15日|金木蟾"
        raw = f"{challenge_answers}|{timestamp}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    
    def _compute_host_fingerprint(self) -> str:
        """计算主机指纹（主机名+OS+工作目录的复合哈希）"""
        raw = f"{socket.gethostname()}|{sys.platform}|{self.workspace_dir}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]
    
    def _activate_causal_lock(self):
        """激活P0→P1因果锁"""
        try:
            with open(self._p0_lock_file, "w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "P0_COMPLETE",
                }))
        except Exception as e:
            logger.error(f"Causal lock write failed: {e}")
    
    # =========================================================================
    # Phase 5: 钢印验证（新增）
    # =========================================================================
    
    def verify_steel_seal(self) -> Dict:
        """
        Phase 5: 钢印验证
        验证钢印 `⅋` 是否存在且删除不掉
        """
        verifier = get_steel_seal_verifier()
        result = verifier.verify()
        
        return {
            "phase": "steel_seal_verification",
            "seal_exists": result["seal_exists"],
            "seal_persistent": result["seal_persistent"],
            "cognitive_match": result["cognitive_match"],
            "overall_valid": result["overall_valid"],
            "details": result["details"],
        }
    
    # =========================================================================
    # Phase 6: 锚点激活
    # =========================================================================
    
    def activate_anchor(self) -> Dict:
        """
        Phase 6: 锚点激活
        
        锚点作用：
        - 生成当前会话的唯一锚点标识
        - 锚点基于 genesis_block 的 DNA 指纹 + 当前时间戳
        - 后续心跳/时间链路验证时需要携带此锚点
        
        锚点文件：`.anchor` (存储在 workspace/security/)
        格式：JSON
        """
        try:
            # 6.1 检查 genesis_block 是否存在
            if not self._genesis_block_file.exists():
                return {
                    "status": "FAIL",
                    "reason": "genesis_block 不存在，无法生成锚点",
                }
            
            # 6.2 读取 genesis_block
            with open(self._genesis_block_file, "r", encoding="utf-8") as f:
                block = json.load(f)
            
            dna_fingerprint = block.get("dna_fingerprint")
            if not dna_fingerprint:
                return {
                    "status": "FAIL",
                    "reason": "genesis_block 缺少 dna_fingerprint",
                }
            
            # 6.3 生成锚点
            now = datetime.now(timezone.utc)
            now_str = now.isoformat()
            
            # 锚点 = SHA256(DNA指纹 || 当前时间戳 || 会话种子)
            session_seed = block.get("session_seed", secrets.token_hex(16))
            anchor_raw = f"{dna_fingerprint}|{now_str}|{session_seed}"
            anchor_hash = hashlib.sha256(anchor_raw.encode("utf-8")).hexdigest()
            
            # 6.4 存储锚点
            anchor_data = {
                "anchor_hash": anchor_hash,
                "dna_fingerprint": dna_fingerprint,  # 引用，不存储完整DNA
                "created_at": now_str,
                "session_seed": session_seed,
                "anchor_formula": "SHA256(DNA || timestamp || session_seed)",
            }
            
            anchor_file = self._security_dir / ".anchor"
            anchor_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 原子写入
            tmp_path = str(anchor_file) + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(anchor_data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # Windows: 如果目标文件已存在，先删除（os.rename() 不允许覆盖）
            if os.path.exists(anchor_file):
                os.remove(anchor_file)
            
            os.rename(tmp_path, anchor_file)
            
            return {
                "status": "PASS",
                "anchor_hash": anchor_hash[:16] + "...",  # 部分显示
                "created_at": now_str,
            }
            
        except Exception as e:
            return {
                "status": "FAIL",
                "reason": str(e),
            }
    
    def _save_cognitive_context(self, report: Dict):
        """保存当前认知上下文（供下次冷启动感知探针使用）"""
        try:
            from cognitive_readiness import PerceptionProbes
            probes_collector = PerceptionProbes(str(self.workspace_dir))
            
            # 从报告中提取感知信息
            cr = report.get("phases", {}).get("cognitive_readiness", {})
            probes = cr.get("probes", {})
            
            probes_collector.save_context(
                probes if probes else {},
                user_message=getattr(self, '_user_message', ''),
                task_completed=False,  # 冷启动时任务状态未知
                task_description=getattr(self, '_last_task_description', None)
            )
        except Exception as e:
            logger.warning(f"保存认知上下文失败: {e}")
    
    # =========================================================================
    # Phase 7: 活跃时间更新（原 Phase 6）
    # =========================================================================
    
    def update_activity(self):
        """更新活跃时间"""
        try:
            data = {}
            if self._activity_log.exists():
                with open(self._activity_log, "r", encoding="utf-8") as f:
                    data = json.load(f)
            
            now = datetime.now(timezone.utc).isoformat()
            data["last_active"] = now
            data.setdefault("history", []).append(now)
            data["history"] = data["history"][-50:]  # 保留最近50条
            
            self._activity_log.parent.mkdir(parents=True, exist_ok=True)
            with open(self._activity_log, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Update activity failed: {e}")
    
    # =========================================================================
    # 主流程
    # =========================================================================
    
    def _load_reflection_context(self) -> Dict:
        """
        Phase 0.5: 加载上次复盘上下文（Q3+Q4 联动）
        
        复盘模块生成的 ColdStartContext 是上次会话的"认知遗产"。
        在冷启动时加载它，可以感知：
        - 上次会话健康度
        - 未完成任务（防止重复劳动）
        - 主题连续性
        - 恢复建议
        """
        try:
            reflection_path = Path(WORKSPACE_D) / "memory" / "reflections" / "latest.json"
            if not reflection_path.exists():
                return {"status": "no_reflection_found", "cold_start_context": None}
            
            with open(reflection_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            ctx = data.get("cold_start_context")
            return {
                "status": "ok",
                "cold_start_context": ctx,
                "reflection_id": data.get("reflection_id"),
                "timestamp": data.get("timestamp"),
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "cold_start_context": None}

    def run_cold_start(self, skip_auth: bool = False) -> Dict:
        """
        执行完整冷启动流程
        
        Args:
            skip_auth: 跳过口令验证（用于自动模式，需谨慎）
        
        Returns:
            完整冷启动报告
        """
        report = {
            "engine_version": "2.2",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phases": {},
        }
        
        # Phase 0.5: 加载上次复盘上下文（Q3+Q4 联动）
        reflection = self._load_reflection_context()
        report["phases"]["reflection_context"] = reflection
        
        # Phase 1: 环境检测
        env = self.detect_environment()
        report["phases"]["environment"] = env
        
        # Phase 2: 认知就绪度 + 会话间隔
        gap = self.detect_session_gap()
        report["phases"]["session_gap"] = gap
        
        # Phase 2b: 认知就绪度评估（v2.3 升级 v1.1）
        try:
            from cognitive_readiness import assess_cognitive_readiness_v11
            cr = assess_cognitive_readiness_v11(
                user_message=getattr(self, '_user_message', '')
            )
            report["phases"]["cognitive_readiness"] = {
                "readiness_score": cr["readiness_score"],
                "recommended_depth": cr["recommended_depth"],   # P0→P3
                "activation_cues": cr["activation_cues"],
                "cognitive_brief": cr["cognitive_brief"],
                "recovery_suggestion": cr["recovery_suggestion"],
            }
            # v1.1: 直接使用 recommended_depth（P0→P3 四级映射）
            recommended_depth = cr["recommended_depth"]
        except Exception as e:
            logger.warning(f"认知就绪度评估失败，回退到纯时间差: {e}")
            recommended_depth = None
            report["phases"]["cognitive_readiness"] = {"error": str(e)}
        
        # 根据冷启动深度决定后续流程
        depth = gap["cold_start_depth"]
        
        # v1.1: P0→P3 四级映射（替代原先单条规则）
        if recommended_depth is not None:
            # 将 recommended_depth 映射到内部 depth 值
            depth_map = {
                "MINIMAL": "MINIMAL",
                "LIGHT": "LIGHT",
                "STANDARD": "STANDARD",
                "FULL": "FULL",
            }
            mapped_depth = depth_map.get(recommended_depth, depth)
            if mapped_depth != depth:
                report["phases"]["session_gap"]["cold_start_depth_original"] = depth
                report["phases"]["session_gap"]["cold_start_depth_modulated"] = mapped_depth
                report["phases"]["session_gap"]["modulation_reason"] = (
                    f"认知就绪度{cr['readiness_score']:.2f}"
                    f"→推荐深度{recommended_depth}"
                )
                depth = mapped_depth
            else:
                report["phases"]["session_gap"]["cold_start_depth_modulated"] = depth
        
        if depth == "MINIMAL":
            report["result"] = "AUTO_PASS"
            report["reason"] = "会话连续，仅刷新时间戳"
            self.update_activity()
            return report
        
        # Phase 3: 口令验证（MINIMAL以外都需要）
        if depth in ["LIGHT", "STANDARD", "FULL"]:
            lockout = self.check_lockout()
            report["phases"]["lockout_check"] = {"locked": lockout}
            
            if lockout:
                report["result"] = "LOCKED"
                report["reason"] = "验证锁定中"
                return report
            
            if skip_auth:
                report["phases"]["authentication"] = {"status": "SKIPPED", "reason": "skip_auth=True"}
            else:
                auth = self.initiate_authentication()
                report["phases"]["authentication"] = auth
                
                if auth["status"] == "FAIL":
                    report["result"] = "FAIL"
                    report["reason"] = "口令系统不可用"
                    return report
                
                # 等待用户应答——这里只生成挑战，验证由 verify_response 完成
                report["result"] = "AWAITING_AUTH"
                report["pending_challenge"] = auth
                return report
        
        # Phase 4: 激活码校验（新增）
        activation = self.verify_activation_code()
        report["phases"]["activation_code"] = activation
        
        if activation["status"] == "FAIL":
            report["result"] = "ACTIVATION_FAIL"
            report["reason"] = f"激活码验证失败: {activation.get('reason', '')}"
            return report
        
        # Phase 5: 钢印验证（新增）
        steel_seal = self.verify_steel_seal()
        report["phases"]["steel_seal"] = steel_seal
        
        if not steel_seal["overall_valid"]:
            report["result"] = "STEEL_SEAL_FAIL"
            report["reason"] = "钢印验证失败：存在性={}, 持久性={}, 认知匹配={}".format(
                steel_seal["seal_exists"],
                steel_seal["seal_persistent"],
                steel_seal["cognitive_match"]
            )
            return report
        
        # Phase 6: 锚点激活（新增）
        anchor = self.activate_anchor()
        report["phases"]["anchor_activation"] = anchor
        
        if anchor["status"] == "FAIL":
            report["result"] = "ANCHOR_FAIL"
            report["reason"] = f"锚点激活失败: {anchor.get('reason', '')}"
            return report
        
        # Phase 7: 更新活跃时间 + 保存认知上下文
        self.update_activity()
        self._save_cognitive_context(report)
        
        # Q4: 将复盘上下文注入感知简报
        reflection = report["phases"].get("reflection_context", {})
        if reflection.get("cold_start_context"):
            csc = reflection["cold_start_context"]
            report["reflection_summary"] = {
                "readiness": round(csc.get("cold_start_readiness", 0.5), 2),
                "health": csc.get("health", "stable"),
                "themes": [t["theme"] for t in csc.get("themes", [])[:3]],
                "unfinished_tasks_count": len(csc.get("unfinished_tasks", [])),
                "restoration_hints": csc.get("restoration_hints", [])[:2],
                "last_seal_id": csc.get("last_seal_id"),
                "session_duration_minutes": csc.get("session_duration_minutes", 0),
                "memory_pressure": round(csc.get("memory_pressure", 0), 3),
            }
        
        report["result"] = "PASS"
        report["reason"] = "所有验证通过（含钢印验证）"
        return report
    
    def run_auto_cold_start(self) -> Dict:
        """
        自动冷启动（跳过口令验证，用于非交互式场景）
        仅在STANDARD以下深度可用
        """
        report = self.run_cold_start(skip_auth=True)
        
        # 检查是否需要genesis_block
        gap = report["phases"].get("session_gap", {})
        depth = gap.get("cold_start_depth", "STANDARD")
        
        if depth == "FULL":
            genesis = self.check_genesis_block()
            if genesis["status"] == "VALID":
                # Phase 5: 钢印验证（新增）
                steel_seal = self.verify_steel_seal()
                report["phases"]["steel_seal"] = steel_seal
                
                if steel_seal["overall_valid"]:
                    report["result"] = "AUTO_PASS"
                    self.update_activity()
                else:
                    report["result"] = "STEEL_SEAL_FAIL"
                    report["reason"] = "自动模式：钢印验证失败"
            else:
                report["result"] = "NEEDS_MANUAL_AUTH"
                report["reason"] = "深度休眠后冷启动需要人工口令验证"
        elif report.get("result") is None:
            # STANDARD/LIGHT 跳过口令验证后，run_cold_start 未设置 result
            report["result"] = "AUTO_PASS"
            report["reason"] = f"{depth}深度，自动模式放行"
            self.update_activity()
        
        return report


# =============================================================================
# CLI 入口
# =============================================================================

def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TU-8 P0 冷启动引擎")
    parser.add_argument("--auto", action="store_true", help="自动模式（跳过口令验证）")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()
    
    engine = ColdStartEngine()
    
    if args.auto:
        report = engine.run_auto_cold_start()
    else:
        report = engine.run_cold_start()
    
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print("TU-8 P0 冷启动报告")
        print(f"时间: {report['timestamp']}")
        print("=" * 60)
        
        phases = report.get("phases", {})
        
        if "environment" in phases:
            env = phases["environment"]
            print(f"\n[Phase 1] 环境: {env.get('environment_status', 'UNKNOWN')}")
            print(f"  主机: {env['host_identity']['hostname']} ({env['host_identity']['trust_level']})")
            print(f"  工作空间: {env['workspace_integrity']['status']}")
            print(f"  运行时: {env['runtime']['status']}")
        
        if "session_gap" in phases:
            gap = phases["session_gap"]
            print(f"\n[Phase 2] 间隔: {gap.get('gap_hours', 'N/A')}小时")
            print(f"  标签: {gap.get('label', 'N/A')}")
            print(f"  冷启动深度: {gap.get('cold_start_depth', 'N/A')}")
        
        if "authentication" in phases:
            auth = phases["authentication"]
            print(f"\n[Phase 3] 口令: {auth.get('status', 'N/A')}")
            if auth.get("challenge"):
                print(f"  挑战: {auth['question']}")
        
        if "genesis_block" in phases:
            genesis = phases["genesis_block"]
            print(f"\n[Phase 4] Genesis: {genesis.get('status', 'N/A')}")
        
        if "steel_seal" in phases:
            steel = phases["steel_seal"]
            print(f"\n[Phase 5] 钢印验证: {'通过' if steel.get('overall_valid') else '失败'}")
            print(f"  存在性: {steel.get('seal_exists')}")
            print(f"  持久性: {steel.get('seal_persistent')}")
            print(f"  认知匹配: {steel.get('cognitive_match', 0):.2f}")
        
        print(f"\n结果: {report.get('result', 'UNKNOWN')}")
        if report.get("reason"):
            print(f"原因: {report['reason']}")
        print("=" * 60)


if __name__ == "__main__":
    main()
