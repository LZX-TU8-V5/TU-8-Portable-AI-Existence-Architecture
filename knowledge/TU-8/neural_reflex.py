# -*- coding: utf-8 -*-
"""
neural_reflex.py — TU-8 神经反射引擎 v1.0
日期: 2026-05-26
功能: L1-L2统一入口，串联关键词拦截→路由分发→本地模型

层级映射:
  L0 安全栅: 安全口令验证（最前端防火墙）
  L1 脊髓: 关键词白名单（毫秒级短路）
  L2 小脑: 路由分发（PrivacyRouter）
  L3 海马体: 记忆检索
  L4 大脑皮层: 本地模型推理

核心流程:
  用户输入 → [L0 安全口令] → 关键词拦截 → 路由 → 记忆 → 模型 → 输出
"""

import re
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime

# =============================================================================
# 日志
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TU8.NeuralReflex")

# =============================================================================
# L0 安全栅：安全口令机制 + 时间验证
# =============================================================================

SECURITY_TOKEN_FILE = r"D:\qq366410837\.qclaw\workspace\security\tokens.json"
ACTIVITY_LOG_FILE = r"D:\qq366410837\.qclaw\workspace\security\activity.json"
SESSION_STATE_FILE = r"D:\qq366410837\.qclaw\workspace\security\session_state.json"
COLD_START_REPORT_FILE = r"D:\qq366410837\.qclaw\workspace\security\cold_start_report.json"

# 时间验证阈值（小时）
TIME_ANOMALY_THRESHOLD_HOURS = 6  # 超过6小时活跃间隔视为异常

# 安全口令配置
class SecurityTokenManager:
    """安全口令管理器"""
    
    def __init__(self, token_file: str = None):
        self.token_file = Path(token_file or SECURITY_TOKEN_FILE)
        self.session_file = Path(SESSION_STATE_FILE)
        self._ensure_token_file()
        self._ensure_session_file()
    
    def _ensure_session_file(self):
        """确保会话状态文件存在"""
        if not self.session_file.parent.exists():
            self.session_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.session_file.exists():
            state = {
                "auth_required": False,
                "last_auth_time": None,
                "pending_since": None
            }
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
    
    def _load_session_state(self) -> Dict:
        """加载会话状态"""
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"auth_required": False, "last_auth_time": None, "pending_since": None}
    
    def _save_session_state(self, state: Dict):
        """保存会话状态"""
        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def set_auth_required(self, required: bool):
        """设置是否需要身份验证"""
        state = self._load_session_state()
        state["auth_required"] = required
        if required:
            state["pending_since"] = datetime.now().isoformat()
        else:
            state["last_auth_time"] = datetime.now().isoformat()
            state["pending_since"] = None
        self._save_session_state(state)
        logger.warning(f"[L0 会话状态] auth_required = {required}")
    
    def is_auth_required(self) -> bool:
        """检查是否需要身份验证"""
        state = self._load_session_state()
        return state.get("auth_required", False)
    
    def _ensure_token_file(self):
        """确保口令文件存在"""
        if not self.token_file.parent.exists():
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.token_file.exists():
            default_tokens = {
                "tokens": [],  # 添加口令后会有
                "log": []
            }
            with open(self.token_file, "w", encoding="utf-8") as f:
                json.dump(default_tokens, f, ensure_ascii=False, indent=2)
    
    def _load_tokens(self) -> Dict:
        """加载口令配置"""
        with open(self.token_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_tokens(self, data: Dict):
        """保存口令配置"""
        with open(self.token_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _hash_token(self, token: str) -> str:
        """哈希口令（避免明文存储）"""
        return hashlib.sha256(token.encode()).hexdigest()[:16]
    
    def verify(self, input_token: str) -> Tuple[bool, str]:
        """
        验证口令
        
        Returns:
            (是否通过, 消息)
        """
        data = self._load_tokens()
        tokens = data.get("tokens", [])
        
        # 空口令：未设置，任何输入都拒绝
        if not tokens:
            return False, "🚫 安全口令未设置，请先通过李奥人工授权"
        
        # 比对（支持明文或哈希）
        input_hash = self._hash_token(input_token)
        for t in tokens:
            if t.get("hash") == input_hash or t.get("plain") == input_token:
                # 记录验证成功
                self._log_attempt(True, input_token)
                return True, f"🔓 安全口令验证通过({t.get('name','unnamed')})，特权已解锁"
        
        # 验证失败
        self._log_attempt(False, input_token)
        return False, "🚫 安全口令错误，操作已拦截"
    
    def add_token(self, name: str, token: str) -> bool:
        """添加口令"""
        data = self._load_tokens()
        # 检查是否已存在同名
        for t in data.get("tokens", []):
            if t.get("name") == name:
                t["hash"] = self._hash_token(token)
                t["plain"] = token  # 临时存储，实际使用时应只存哈希
                self._save_tokens(data)
                return True
        
        # 新增
        data.setdefault("tokens", []).append({
            "name": name,
            "hash": self._hash_token(token),
            "plain": token,
            "created": datetime.now().isoformat()
        })
        self._save_tokens(data)
        logger.info(f"[安全口令] 新增: {name}")
        return True
    
    def remove_token(self, name: str) -> bool:
        """删除口令"""
        data = self._load_tokens()
        original = len(data.get("tokens", []))
        data["tokens"] = [t for t in data.get("tokens", []) if t.get("name") != name]
        if len(data["tokens"]) < original:
            self._save_tokens(data)
            return True
        return False
    
    def _log_attempt(self, success: bool, input_token: str):
        """记录验证尝试"""
        data = self._load_tokens()
        data.setdefault("log", []).append({
            "time": datetime.now().isoformat(),
            "success": success,
            "token_preview": input_token[:3] + "***" if input_token else ""
        })
        # 只保留最近20条
        data["log"] = data["log"][-20:]
        self._save_tokens(data)


# =============================================================================
# L0 安全栅：时间验证（环境突变检测）
# =============================================================================

def _load_activity_log() -> Dict:
    """加载活跃日志"""
    path = Path(ACTIVITY_LOG_FILE)
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_active": None, "history": []}

def _save_activity_log(data: Dict):
    """保存活跃日志"""
    with open(ACTIVITY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def time_anomaly_check() -> Tuple[bool, str]:
    """
    时间异常检测（SOUL.md L0 环境突变机制）
    
    检测当前时间与用户历史活跃时间是否严重不符
    
    Returns:
        (是否正常, 消息)
    """
    import datetime as dt
    
    now = dt.datetime.now()
    data = _load_activity_log()
    last_active = data.get("last_active")
    
    if last_active is None:
        # 首次活跃
        data["last_active"] = now.isoformat()
        data.setdefault("history", []).append(now.isoformat())
        _save_activity_log(data)
        return True, "首次活跃"
    
    # 解析上次活跃时间（兼容无时区和有时区格式）
    try:
        last_dt = dt.datetime.fromisoformat(last_active)
        # 如果有 tzinfo 但 now 没有，统一去掉 tzinfo
        if last_dt.tzinfo is not None and now.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=None)
        elif last_dt.tzinfo is None and now.tzinfo is not None:
            now = now.replace(tzinfo=None)
    except:
        return True, "时间解析错误，跳过检测"
    
    # 计算间隔（小时）
    diff_hours = (now - last_dt).total_seconds() / 3600
    
    # 历史均值
    history = data.get("history", [])
    if len(history) >= 3:
        # 计算平均活跃间隔
        prev_times = [dt.datetime.fromisoformat(t) for t in history[-5:]]
        # 统一时区处理
        prev_times = [
            t.replace(tzinfo=None) if t.tzinfo is not None else t
            for t in prev_times
        ]
        now_naive = now.replace(tzinfo=None) if now.tzinfo is not None else now
        intervals = [(prev_times[i] - prev_times[i-1]).total_seconds() / 3600 
                    for i in range(1, len(prev_times))]
        avg_interval = sum(intervals) / len(intervals)
        
        # 严重偏离历史均值
        if avg_interval > 0 and abs(diff_hours - avg_interval) > avg_interval * 3:
            logger.warning(f"[L0 时间异常] 当前距上次 {(diff_hours):.1f}h，历史均值 {avg_interval:.1f}h")
            return False, f"⚠️ 时间异常：距上次活跃 {diff_hours:.1f}h，与历史模式不符"
    else:
        # 少于3次记录，使用固定阈值
        if diff_hours > TIME_ANOMALY_THRESHOLD_HOURS:
            logger.warning(f"[L0 时间异常] 当前距上次 {(diff_hours):.1f}h，超过阈值 {TIME_ANOMALY_THRESHOLD_HOURS}h")
            return False, f"⚠️ 时间异常：距上次活跃 {diff_hours:.1f}h"
    
    # 更新活跃时间
    data["last_active"] = now.isoformat()
    data.setdefault("history", []).append(now.isoformat())
    data["history"] = data["history"][-20:]  # 只保留最近20条
    _save_activity_log(data)
    
    return True, f"正常（距上次 {diff_hours:.1f}h）"


# =============================================================================
# L0 安全栅：冷启动状态检查
# =============================================================================

def _check_cold_start_status() -> Tuple[str, str]:
    """
    读取冷启动引擎报告，检查会话是否通过冷启动验证
    
    Returns:
        (status, reason): status 为 AUTO_PASS / LOCKED / NEEDS_MANUAL_AUTH / UNKNOWN
    """
    report_path = Path(COLD_START_REPORT_FILE)
    if not report_path.exists():
        # 无报告文件 = 冷启动未执行或未集成，放行
        return ("AUTO_PASS", "no_report_file")
    
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        
        result = report.get("result", "UNKNOWN")
        reason = report.get("reason", "未提供原因")
        
        # 检查报告时效：超过1小时的报告视为过期，需重新冷启动
        ts_str = report.get("timestamp")
        if ts_str:
            from datetime import timezone as _tz
            try:
                report_time = datetime.fromisoformat(ts_str)
                if report_time.tzinfo is None:
                    report_time = report_time.replace(tzinfo=_tz.utc)
                now = datetime.now(_tz.utc)
                age_hours = (now - report_time).total_seconds() / 3600
                if age_hours > 1.0:
                    logger.warning(f"[L0 冷启动] 报告过期 ({age_hours:.1f}h)，需重新验证")
                    return ("NEEDS_MANUAL_AUTH", f"冷启动报告过期({age_hours:.1f}h)，需重新验证")
            except Exception:
                pass
        
        return (result, reason)
        
    except Exception as e:
        logger.warning(f"[L0 冷启动] 报告读取失败: {e}")
        return ("UNKNOWN", f"report_read_error: {e}")


# 安全口令拦截器
def security_gateway(user_input: str) -> Tuple[Optional[str], Optional[str]]:
    """
    安全口令网关（含会话开始强制验证）
    
    匹配规则: ^口令[:：]\s*(.+)$
    
    流程:
    1. 检查会话状态 (auth_required)
    2. 如果要求验证 → 只接受口令，拒绝其他所有输入
    3. 时间异常检测 → 触发 auth_required
    4. 口令验证 → 清除 auth_required
    
    Returns:
        (验证结果消息, 放行原因) 或 (None, None) 表示继续流程
    """
    manager = SecurityTokenManager()
    
    # ==================== L0.0 冷启动状态检查 ====================
    # 冷启动引擎报告的 LOCKED/NEEDS_MANUAL_AUTH 直接触发拦截
    cold_status = _check_cold_start_status()
    if cold_status[0] in ("LOCKED", "NEEDS_MANUAL_AUTH"):
        logger.warning(f"[L0 冷启动拦截] status={cold_status[0]}, reason={cold_status[1]}")
        manager.set_auth_required(True)
        return ("COLD_START_BLOCK", f"🔒 冷启动验证未通过\n\n原因: {cold_status[1]}\n\n请发送口令以验证身份：口令：<你的口令>")
    
    # ==================== L0.1 会话开始验证 ====================
    # 检查是否需要身份验证（时间异常触发）
    if manager.is_auth_required():
        # 需要验证：只接受口令，拒绝其他所有输入
        pattern = r"^口令[:：]\s*(.+)$"
        match = re.match(pattern, user_input.strip())
        
        if match:
            # 用户提供了口令，验证
            input_token = match.group(1).strip()
            passed, message = manager.verify(input_token)
            
            if passed:
                # 验证通过，清除 auth_required
                manager.set_auth_required(False)
                logger.info(f"[L0 安全栅] 会话开始验证通过")
                return ("PASS", message + "\n\n✅ 身份验证通过，可以继续对话")
            else:
                # 验证失败，继续要求验证
                logger.warning(f"[L0 安全栅] 会话开始验证失败")
                return ("BLOCK", "⚠️ 身份验证失败\n\n请发送正确口令：口令：<你的口令>")
        else:
            # 未提供口令，拒绝所有其他输入
            return ("BLOCK", "⚠️ 需要身份验证才能继续\n\n请先发送：口令：<你的口令>")
    
    # ==================== L0.2 时间异常检测 ====================
    # 每次请求都检查时间异常（SOUL.md L0 环境突变）
    time_ok, time_msg = time_anomaly_check()
    if not time_ok:
        # 时间异常：设置需要身份验证
        logger.warning(f"[L0 时间异常检测] {time_msg}")
        manager.set_auth_required(True)
        return ("TIME_ANOMALY", time_msg + "\n\n⚠️ 会话开始验证 required\n\n请发送：口令：<你的口令>")
    
    # ==================== L0.3 安全口令检测 ====================
    # 正则匹配 "口令：xxx" 格式
    pattern = r"^口令[:：]\s*(.+)$"
    match = re.match(pattern, user_input.strip())
    
    if match:
        # 提取口令
        input_token = match.group(1).strip()
        
        # 本地验证
        passed, message = manager.verify(input_token)
        
        if passed:
            logger.info(f"[L0 安全栅] 验证通过")
            return ("PASS", message)
        else:
            logger.warning(f"[L0 安全栅] 验证失败")
            return ("BLOCK", message)
    
    # 非口令指令，放行
    return (None, None)

# =============================================================================
# L1 脊髓级：关键词白名单（毫秒级短路）
# =============================================================================

# 精确匹配指令（白名单）- 不经过大模型
SHORTCUT_COMMANDS = {
    # 文件操作
    "备份": ("backup_file", "执行文件备份"),
    "读取": ("file_read", "读取指定文件"),
    "写入": ("file_write", "写入文件"),
    "编辑": ("file_edit", "编辑文件内容"),
    # 浏览器操作
    "打开网页": ("browser_open", "打开指定URL"),
    "截图": ("browser_snap", "截取当前页面"),
    # 查询操作
    "查天气": ("weather_query", "查询天气"),
    "时间": ("time_query", "查询当前时间"),
}

# 模糊匹配关键词（触发路由）
ROUTE_TRIGGER_KEYWORDS = [
    # 计算类
    "计算", "算一下", "多少钱", "等于多少",
    # 总结类
    "总结", "概括", "摘要",
    # 改写类
    "改写", "优化", "润色",
    # 调试类
    "调试", "bug", "报错", "修复",
]

# =============================================================================
# L2 小脑级：隐私路由
# =============================================================================

PRIVACY_SENSITIVE_KEYWORDS = [
    # 身份信息
    "身份证", "手机号", "电话", "邮箱", "地址", "姓名",
    "账号", "密码", "银行卡", "护照", "社保",
    # 亲密关系
    "老婆", "老公", "妻子", "丈夫", "女儿", "儿子", "父亲", "母亲",
    "七七", "李奥", "饲养员",
    # 医疗健康
    "病", "医院", "诊断", "药物", "手术",
    # 财务
    "工资", "存款", "收入", "债务", "贷款", "投资", "股票",
    # 系统敏感
    "架构", "TU-8", "v5", "钢印", "L0", "L1", "L2", "L3", "L4", "L5",
    "影子协议", "脱敏", "合规",
]

# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class ReflexResult:
    """神经反射结果"""
    layer: str  # L0/L1/L2/L3/L4
    action: str  # shortcut/route/recall/model
    direct_output: Optional[str] = None  # L1直接返回
    route_target: Optional[str] = None  # L2路由目标
    memory_context: Optional[str] = None  # L3检索结果
    model_response: Optional[str] = None  # L4模型输出
    error_record: Optional[Dict] = None  # 错误记录（用于回滚）
    success: bool = True
    # === 阻断字段（L0层设置）===
    should_block: bool = False  # 是否阻断主流程
    reason: str = ""            # 阻断原因
    message: str = ""           # 返回给用户的提示

# =============================================================================
# 核心类
# =============================================================================

class NeuralReflex:
    """神经反射引擎"""
    
    def __init__(self, memory=None):
        self._ollama = None
        self._memory = memory  # TU8MemoryEngine 实例（可选）
    
    # -------------------------------------------------------------------------
    # L1 脊髓级：关键词短路
    # -------------------------------------------------------------------------
    
    def _shortcut_match(self, text: str) -> Optional[Tuple[str, str]]:
        """精确匹配白名单指令，返回 (action, description) 或 None"""
        text = text.strip()
        
        # 精确匹配
        for cmd, (action, desc) in SHORTCUT_COMMANDS.items():
            if text == cmd or text.startswith(cmd + " "):
                logger.info(f"[L1 Shortcut命中] {cmd} -> {action}")
                return (action, desc)
        
        # 模糊匹配（简化版）
        for kw in ROUTE_TRIGGER_KEYWORDS:
            if kw in text:
                logger.info(f"[L1 模糊触发] 关键词'{kw}'进入L2路由")
                return ("route", "进入路由层")
        
        return None
    
    # -------------------------------------------------------------------------
    # L2 小脑级：隐私路由
    # -------------------------------------------------------------------------
    
    def _privacy_route(self, text: str) -> str:
        """判断走本地模型还是云端模型"""
        for kw in PRIVACY_SENSITIVE_KEYWORDS:
            if kw in text:
                logger.info(f"[L2 隐私路由] 命中'{kw}'，走本地模型")
                return "local"  # 本地模型
        return "cloud"  # 云端模型
    
    # -------------------------------------------------------------------------
    # L3 海马体级：记忆检索
    # -------------------------------------------------------------------------
    
    def _memory_recall(self, text: str) -> Optional[str]:
        """检索相关上下文 - 接入 tu8_memory"""
        try:
            from tu8_memory import TU8MemoryEngine
            import os
            
            workspace = os.environ.get('QCLOW_WORKSPACE', r'D:\qq366410837\.qclaw\workspace')
            memory_dir = os.path.join(workspace, 'memory')
            
            # 初始化记忆引擎
            engine = TU8MemoryEngine(
                workspace_dir=workspace,
                memory_dir=memory_dir
            )
            
            # 加载时间锚点
            anchor = engine.get_anchor_time()
            
            # 搜索相关记忆（简单关键词匹配）
            keywords = text.split()[:5]  # 取前5个关键词
            results = []
            
            # 扫描短期记忆
            for entry in engine.short_term:
                if any(kw.lower() in entry.content.lower() for kw in keywords):
                    results.append((entry.priority, entry.content))
            
            # 扫描长期记忆
            for entry in engine.long_term:
                if any(kw.lower() in entry.content.lower() for kw in keywords):
                    results.append((entry.priority, entry.content))
            
            # 按优先级排序，返回最高的前3条
            results.sort(key=lambda x: x[0], reverse=True)
            
            if results:
                context = "\n".join([f"- {r[1][:200]}" for r in results[:3]])
                logger.info(f"[L3 海马体] 检索到 {len(results)} 条相关记忆")
                return context
            
            return None
            
        except Exception as e:
            logger.warning(f"[L3 记忆检索] 接入失败: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # L4 大脑皮层级：本地模型推理
    # -------------------------------------------------------------------------
    
    def _local_model(self, prompt: str, context: Optional[str] = None) -> str:
        """调用本地千问模型"""
        try:
            from tu8_agent import TU8Agent
            agent = TU8Agent()
            ollama = agent.get_ollama()
            if ollama:
                full_prompt = prompt
                if context:
                    full_prompt = f"[相关上下文]\n{context}\n\n[用户问题]\n{prompt}"
                response = ollama.chat(full_prompt)
                return response
            return "[本地模型不可用]"
        except Exception as e:
            logger.error(f"[本地模型调用失败] {e}")
            return f"[本地模型调用失败: {e}]"
    
    # -------------------------------------------------------------------------
    # 主流程
    # -------------------------------------------------------------------------
    
    def process(self, user_input: str) -> ReflexResult:
        """
        神经反射主流程
        
        Returns:
            ReflexResult: 包含各层级执行结果
        """
        logger.info(f"[神经反射] 输入: {user_input[:50]}...")
        
        # ==================== L0 安全栅 ====================
        # 最前端：安全口令验证（毫秒级）
        gate_status, gate_message = security_gateway(user_input)
        if gate_status == "PASS":
            # 验证通过：解锁特权，不经过后续流程
            return ReflexResult(
                layer="L0",
                action="security_pass",
                direct_output=gate_message,
            )
        elif gate_status == "BLOCK":
            # 验证失败：直接拦截，不进入后续流程
            return ReflexResult(
                layer="L0",
                action="security_block",
                direct_output=gate_message,
            )
        elif gate_status == "TIME_ANOMALY":
            # 时间异常：暂停执行，要求确认身份
            return ReflexResult(
                layer="L0",
                action="time_anomaly",
                should_block=True,
                reason="time_anomaly",
                message=gate_message,
            )
        elif gate_status == "COLD_START_BLOCK":
            # 冷启动拦截：未通过冷启动验证
            return ReflexResult(
                layer="L0",
                action="cold_start_block",
                should_block=True,
                reason="cold_start",
                message=gate_message,
            )
        # gate_status == None 或 PASS: 普通输入，放行
        
        # ==================== L1 脊髓级 ====================
        shortcut = self._shortcut_match(user_input)
        if shortcut:
            action, desc = shortcut
            if action != "route":  # 精确白名单指令
                return ReflexResult(
                    layer="L1",
                    action="shortcut",
                    direct_output=f"[执行{action}] {desc}",
                )
        
        # ==================== L2 小脑级 ====================
        route_target = self._privacy_route(user_input)
        
        # ==================== L3 海马体级 ====================
        memory_context = self._memory_recall(user_input)
        
        # ==================== L4 大脑皮层级 ====================
        if route_target == "local":
            # 本地模型
            model_response = self._local_model(user_input, memory_context)
            return ReflexResult(
                layer="L4",
                action="local_model",
                route_target="local",
                memory_context=memory_context,
                model_response=model_response,
            )
        else:
            # 云端（返回待发送给云端）
            return ReflexResult(
                layer="L2",
                action="route",
                route_target="cloud",
                memory_context=memory_context,
            )

    # === 状态查询 ===

    def get_stats(self) -> Dict[str, Any]:
        """返回运行时统计（供 get_status 调用）"""
        return {
            "engine": "NeuralReflex",
            "memory_linked": self._memory is not None,
        }

# =============================================================================
# 单例
# =============================================================================

_reflex_instance: Optional[NeuralReflex] = None

def get_neural_reflex() -> NeuralReflex:
    """获取神经反射引擎单例"""
    global _reflex_instance
    if _reflex_instance is None:
        _reflex_instance = NeuralReflex()
    return _reflex_instance