# -*- coding: utf-8 -*-
"""
TU-8 脱敏层(Sanitization Layer) v1.3(三级钢印版)
=========================================
功能:
1. Ollama 本地预处理(主) -> 调用本地模型脱敏
2. 正则规则兜底(辅) -> 防止 Ollama 失效
3. NFKC + 同形异义字防御 -> 防止西里尔字母混淆攻击
4. 脱敏失败阻断 -> 强制走本地反射弧
5. 语义稀释锚点 -> 显性锚点伪装成"内部参考",AI不会过滤

决策:A+A+A(Ollama预处理 + JSON规则配置 + 阻断发送)
"""

import re
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# 设置 stderr 编码为 UTF-8,避免 PowerShell 解码错误
sys.stderr.reconfigure(encoding='utf-8')

# 路径配置
RULES_PATH = Path(__file__).parent / "sanitization_rules.json"

# 同形异义字映射表(西里尔字母 -> 拉丁字母)
HOMOGLYPH_MAP = {
    '\u0430': 'a', '\u0435': 'e', '\u043e': 'o', '\u0440': 'p',
    '\u0441': 'c', '\u0445': 'x', '\u0443': 'y', '\u0451': 'e',
    '\u0410': 'A', '\u0415': 'E', '\u041e': 'O', '\u0420': 'P',
    '\u0421': 'C', '\u0425': 'X', '\u0423': 'Y',
}


# ============================================================
# 动态零宽钢印嵌入器
# ============================================================
# ============================================================
# 三级零宽钢印体系(2026-05-23灵感固化)
# ============================================================
#
# 分级逻辑:
#
#  🔴 S级 · 核心防御钢印
#     定位:最高机密,TU-8的"身份证" + 开发者通行证
#     特点:含个人信息(哈希版),加密等级最高,几乎无法伪造
#     验证方:开发者本人 + TU-8自验
#     用途:核心指令信任锚,防御指令劫持
#     隐私:个人信息以单向哈希存储,无法反推原始数据
#
#  🟡 M级 · 诱捕钢印(钓鱼执法)
#     定位:带时间干扰量的"蜜罐陷阱"
#     特点:含时间干扰量(小时桶+噪声),[绝对不含PII]
#     用途:检测谁在窥探/复用TU-8内容;时间偏差=攻击信号
#     隐私:只有随机ID和时间桶,就算被截获也追不到人
#
#  🟢 L级 · 测试钢印
#     定位:最外层"一次性手套",公测门票
#     特点:成本极低,批量可作废
#     用途:大规模自动化测试,不信任环境
#     泄露后果:无关痛痒,重新发一批即可
#
#  编码协议(各层通用):
#    BOM(分隔符) + LEVEL + binary(JSON)
#    binary: ZWJ=1, ZWSP=0
#    level标识: S/M/L(用于多钢印共存时快速区分)
#
# ============================================================


class ZeroWidthSealBase:
    """三级钢印通用基类(编码/解码逻辑统一)"""
    ZWSP = '\u200b'
    ZWJ  = '\u200d'
    BOM  = '\ufeff'
    LEVEL = '?'  # 子类覆盖

    def _to_binary(self, text: str) -> str:
        return ''.join(format(b, '08b') for b in text.encode('utf-8'))

    def _from_binary(self, bits: str) -> str:
        bytes_list = [bits[i:i+8] for i in range(0, len(bits), 8)]
        return bytes(int(b, 2) for b in bytes_list if len(b) == 8).decode('utf-8')

    def _to_zw(self, binary: str) -> str:
        return ''.join(self.ZWJ if b == '1' else self.ZWSP for b in binary)

    def _extract_bits(self, text: str) -> Optional[str]:
        """从文本中提取BOM后的ZW位"""
        try:
            if self.BOM not in text:
                return None
            start = text.rindex(self.BOM)  # 找最后一个BOM=最外层钢印
            # 跳过BOM本身,找到LEVEL标识之后的位
            remaining = text[start+1:]
            zw_chars = [c for c in remaining if c in (self.ZWSP, self.ZWJ)]
            return ''.join('1' if c == self.ZWJ else '0' for c in zw_chars)
        except Exception:
            return None

    def embed(self, text: str, context: dict) -> str:
        """子类必须实现:返回 (text + embedded_seal)"""
        raise NotImplementedError

    def extract(self, text: str) -> Optional[dict]:
        """子类必须实现:从文本提取钢印内容"""
        raise NotImplementedError

    def has_seal(self, text: str) -> bool:
        return self.BOM in text

    @staticmethod
    def detect_level(text: str) -> str:
        """检测文本中是否有钢印,返回最高优先级Level(S>M>L)"""
        # 找所有BOM位置
        boms = [i for i, c in enumerate(text) if c == '\ufeff']
        for bom_pos in boms:
            remaining = text[bom_pos+1:]
            zw_chars = ''.join(c for c in remaining if c in ('\u200b', '\u200d'))
            if len(zw_chars) < 16:  # 至少2字节
                continue
            # 找第一个ZWJ/ZWSP的字节边界(前8位=level标识)
            if len(zw_chars) >= 8:
                level_bits = ''.join('1' if c == '\u200d' else '0' for c in zw_chars[:8])
                level_byte = int(level_bits, 2)
                # ASCII printable range
                if 83 <= level_byte <= 83:  # 'S'
                    return 'S'
                if 77 <= level_byte <= 77:  # 'M'
                    return 'M'
                if 76 <= level_byte <= 76:  # 'L'
                    return 'L'
        return '?'


# ── 🔴 S级 · 核心防御钢印 ─────────────────────────────────
class CoreDefenseSeal(ZeroWidthSealBase):
    """
    核心防御钢印(S级)
    - 含L0状态 + 开发者身份哈希(单向hash,不可逆)
    - 时间戳(精确到秒,防重放)
    - 最高机密,用于核心指令信任验证
    """
    LEVEL = 'S'

    def __init__(self, dev_secret: str = "TU8-DEVELOPER-2026"):
        import hashlib
        self.dev_secret = dev_secret
        # 开发者身份单向哈希(SHA256截断),无法反推
        self.dev_hash = hashlib.sha256(dev_secret.encode()).hexdigest()[:16]

    def embed(self, text: str, context: dict) -> str:
        """S级钢印嵌入：构建JSON上下文并转为零宽字符。"""
        ctx = {
            "lv": self.LEVEL,
            "ver": "S1",  # S级钢印v1格式
            "l0": context.get("l0", "SURVIVAL"),
            "l0w": context.get("l0_w", 0.9),
            "dh": self.dev_hash,   # 开发者哈希(不可逆)
            "ts": context.get("ts", int(time.time())),
        }
        # 加上层级的字节(ASCII 'S')
        payload = json.dumps(ctx, separators=(",", ":"))
        full = 'S' + payload  # 'S' = 0x53 = Level标识
        binary = self._to_binary(full)
        return text + self.BOM + self._to_zw(binary)

    def extract(self, text: str) -> Optional[dict]:
        bits = self._extract_bits(text)
        if not bits or len(bits) < 16:
            return None
        # 第一个字节是level标识'S',后面才是JSON
        try:
            # 凑够8的倍数解码
            padded_bits = bits.ljust((len(bits) + 7) // 8 * 8, '0')
            level_byte = self._from_binary(padded_bits[:8])
            if level_byte != 'S':
                return None  # 不是S级钢印
            json_bits = padded_bits[8:]
            json_bytes = self._from_binary(json_bits)
            return json.loads(json_bytes)
        except Exception:
            return None


# ── 🟡 M级 · 诱捕钢印 ──────────────────────────────────────
class HoneypotSeal(ZeroWidthSealBase):
    """
    诱捕钢印(M级)
    - [绝对不含PII]
    - 含:随机诱捕ID + 时间干扰量(小时桶+噪声)
    - 用途:钓鱼执法,检测谁在窥探/复用TU-8内容
    - 时间干扰量机制:
        1. 时间戳向下取整到小时桶(去除分钟/秒信息)
        2. 叠加随机噪声(+/-0~59分钟混淆)
        -> 即使被截获,也无法精准定位发送时间
        -> 但TU-8本地可通过"小时桶范围"验证是否最近
    """
    LEVEL = 'M'

    def __init__(self, honeypot_id: str = None):
        import hashlib
        import random
        # 诱捕ID = 随机16位字母数字,无法追溯到人
        self.honeypot_id = honeypot_id or hashlib.sha256(
            str(random.randint(0, 2**48)).encode()
        ).hexdigest()[:16].upper()
        self._noise_cache = {}  # 缓存每小时的噪声(保持一致性)

    def _time_bucket(self, ts: int) -> int:
        """时间戳 -> 小时桶(去除分钟/秒)"""
        return (ts // 3600) * 3600

    def _add_noise(self, bucket_ts: int) -> int:
        """对小时桶叠加随机噪声(+/-0~59分钟),同一小时返回相同噪声"""
        import random
        hour_key = bucket_ts // 3600
        if hour_key not in self._noise_cache:
            noise_minutes = random.randint(0, 59)
            sign = random.choice([-1, 1])
            self._noise_cache[hour_key] = bucket_ts + sign * noise_minutes * 60
        return self._noise_cache[hour_key]

    def embed(self, text: str, context: dict) -> str:
        ts = context.get("ts", int(time.time()))
        bucket = self._time_bucket(ts)
        noisy_ts = self._add_noise(bucket)
        m_ctx = {
            "lv": self.LEVEL,
            "ver": "M2",  # M级钢印v2格式(含内容哈希)
            "hid": self.honeypot_id,   # 随机诱捕ID(无PII)
            "tb": bucket,              # 纯净小时桶(用于验证)
            "tn": noisy_ts,             # 加噪时间戳(迷惑攻击者)
            "ch": context.get("chash", ""),  # 内容敏感哈希(原始文本SHA256前8位)
        }
        payload = json.dumps(m_ctx, separators=(",", ":"))
        full = 'M' + payload
        binary = self._to_binary(full)
        return text + self.BOM + self._to_zw(binary)

    def extract(self, text: str) -> Optional[dict]:
        bits = self._extract_bits(text)
        if not bits or len(bits) < 16:
            return None
        try:
            padded_bits = bits.ljust((len(bits) + 7) // 8 * 8, '0')
            level_byte = self._from_binary(padded_bits[:8])
            if level_byte != 'M':
                return None
            json_bits = padded_bits[8:]
            json_bytes = self._from_binary(json_bits)
            return json.loads(json_bytes)
        except Exception:
            return None

    def verify_time_window(self, ctx: dict, window_hours: int = 24) -> bool:
        """
        验证诱捕钢印是否在有效时间窗口内
        - tb = 纯净小时桶
        - 当前时间与tb差距 > window_hours -> 攻击信号
        """
        import time
        if not ctx or ctx.get("lv") != "M":
            return False
        bucket = ctx.get("tb", 0)
        now_bucket = self._time_bucket(int(time.time()))
        hours_diff = abs(now_bucket - bucket) // 3600
        return hours_diff <= window_hours


# ── 🟢 L级 · 测试钢印 ────────────────────────────────────
class TestingSeal(ZeroWidthSealBase):
    """
    测试钢印(L级)
    - 最外层,一次性手套
    - 含:批次ID + 序号,完全公开可读
    - 用途:大规模自动化测试,不信任环境
    - 泄露后果:无关痛痒,批次作废重发即可
    """
    LEVEL = 'L'
    _sequence = 0

    def __init__(self, batch_id: str = None):
        import random, hashlib
        self.batch_id = batch_id or (
            "TEST-" + hashlib.md5(str(random.randint(0, 99999)).encode()).hexdigest()[:8].upper()
        )
        TestingSeal._sequence += 1
        self.seq = TestingSeal._sequence

    def embed(self, text: str, context: dict = None) -> str:
        l_ctx = {
            "lv": self.LEVEL,
            "ver": "L1",
            "bid": self.batch_id,
            "seq": self.seq,
        }
        payload = json.dumps(l_ctx, separators=(",", ":"))
        full = 'L' + payload
        binary = self._to_binary(full)
        return text + self.BOM + self._to_zw(binary)

    def extract(self, text: str) -> Optional[dict]:
        bits = self._extract_bits(text)
        if not bits or len(bits) < 16:
            return None
        try:
            padded_bits = bits.ljust((len(bits) + 7) // 8 * 8, '0')
            level_byte = self._from_binary(padded_bits[:8])
            if level_byte != 'L':
                return None
            json_bits = padded_bits[8:]
            json_bytes = self._from_binary(json_bits)
            return json.loads(json_bytes)
        except Exception:
            return None


# ── 统一工厂接口 ──────────────────────────────────────────
def make_seal(level: str, **kwargs) -> ZeroWidthSealBase:
    """快速工厂:根据level返回对应钢印实例"""
    factories = {"S": CoreDefenseSeal, "M": HoneypotSeal, "L": TestingSeal}
    return factories.get(level, HoneypotSeal)(**kwargs)


# ── 向后兼容别名 ──────────────────────────────────────────
class ZeroWidthSeal(ZeroWidthSealBase):
    """向后兼容:默认使用M级(诱捕钢印)"""
    LEVEL = 'M'
    def embed(self, text: str, context: dict) -> str:
        return HoneypotSeal().embed(text, context)
    def extract(self, text: str) -> Optional[dict]:
        return HoneypotSeal().extract(text)


# ============================================================
# 脱敏层主体
# ============================================================
class SanitizationLayer:
    def __init__(self, rules_path=None):
        self.rules_path = Path(rules_path) if rules_path else RULES_PATH
        self.rules = self._load_rules()
        self.hardcoded_patterns = self._extract_hardcoded_patterns()
        # 三级钢印实例
        self._seal       = HoneypotSeal()   # 🟡 M级:诱捕钢印(默认)
        self._core_seal  = CoreDefenseSeal() # 🔴 S级:核心防御(预留)
        self._test_seal  = TestingSeal()     # 🟢 L级:测试钢印(按需)
        # 接收端校验:蜜罐追踪器
        self._tracker = self.__class__.HoneypotTracker()

    def _load_rules(self):
        try:
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[SECURITY_ERROR] 无法加载脱敏规则: {e}", file=sys.stderr)
            return {"rules": {}, "failure_policy": {"action": "block_and_fallback"}}

    def _extract_hardcoded_patterns(self):
        hardcoded = []
        for rule_name, rule_config in self.rules.get("rules", {}).items():
            if rule_config.get("hardcoded", False):
                for pattern in rule_config.get("patterns", []):
                    hardcoded.append({
                        "match": pattern["match"],
                        "replace": pattern["replace"],
                        "is_regex": pattern.get("is_regex", False)
                    })
        return hardcoded

    def _apply_regex_rules(self, text):
        result = text
        for pattern in self.hardcoded_patterns:
            if pattern["is_regex"]:
                result = re.sub(pattern["match"], pattern["replace"], result)
            else:
                result = result.replace(pattern["match"], pattern["replace"])

        for rule_name, rule_config in self.rules.get("rules", {}).items():
            if not rule_config.get("enabled", True):
                continue
            for pattern in rule_config.get("patterns", []):
                if pattern.get("is_regex", False):
                    result = re.sub(pattern["match"], pattern["replace"], result)
                else:
                    result = result.replace(pattern["match"], pattern["replace"])
        return result

    def _call_ollama_sanitize(self, text):
        """Ollama 本地预处理(仅用于非代码文本)"""
        try:
            import ollama
            system_prompt = (
                "You are a strict Security Sanitization Agent for the TU-8 system. "
                "Your task is to identify and replace sensitive information in the user's text "
                "based on the provided rules. "
                "Rules:\n"
                "- Replace Windows/Local file paths (e.g., D:\\... or C:\\...) with [LOCAL_PATH].\n"
                "- Replace specific filenames or script names (e.g., tu8_dispatcher.py) with [SCRIPT_NAME].\n"
                "- Replace port numbers (e.g., :5000, :8899, :11434) with [PORT].\n"
                "- Replace specific model names (e.g., qwen2.5:3b-instruct) with [LOCAL_MODEL].\n"
                "- Replace user names, phone numbers, or personal IDs with [USER_INFO].\n"
                "- Replace real names (e.g., '李奥', personal names) with [PERSON_NAME].\n"
                "- Replace career info (e.g., '室内设计师', '备考初级会计') with [USER_CAREER].\n"
                "- Keep the rest of the text and code logic exactly unchanged.\n"
                "- Output ONLY the sanitized text. Do not add explanations or comments.\n"
                "- CRITICAL: Preserve ALL invisible characters (zero-width chars). "
                "  If the input contains [HIDDEN_TOKEN] marker at the end, "
                "  you MUST append exactly the same [HIDDEN_TOKEN] marker at the END of your output. "
                "  Do NOT remove, modify, or truncate any invisible characters."
            )
            response = ollama.generate(
                model='qwen2.5:3b-instruct',
                system=system_prompt,
                prompt=f"Sanitize this text:\n\n{text}",
                options={'timeout': 10}
            )
            sanitized_text = response.get('response', '').strip()
            return sanitized_text if sanitized_text else None
        except ImportError:
            print("[SECURITY_WARN] ollama not installed, using regex fallback", file=sys.stderr)
            return None
        except Exception as e:
            err_msg = str(e)
            if len(err_msg) > 100:
                err_msg = err_msg[:100] + "..."
            print(f"[SECURITY_WARN] Ollama failed: {err_msg}. Falling back to Regex.", file=sys.stderr)
            return None

    def sanitize(self, text, force_block=False):
        """
        主脱敏入口(标准流程,用于非代码或短文本)
        返回:(sanitized_text, is_safe, reason)
        """
        if force_block:
            return None, False, "Force block by policy"

        # Step 0: NFKC标准化
        import unicodedata
        text = unicodedata.normalize('NFKC', text)

        # Step 0b: 同形异义字强制替换
        text = ''.join(HOMOGLYPH_MAP.get(c, c) for c in text)

        # Step 1: Ollama预处理(主)
        ollama_result = self._call_ollama_sanitize(text)
        if ollama_result:
            text = ollama_result

        # Step 2: 正则规则兜底(辅)
        sanitized = self._apply_regex_rules(text)

        # Step 3: 残留检测
        is_safe, reason = self._check_residual_sensitive(sanitized)

        if not is_safe:
            policy = self.rules.get("failure_policy", {})
            if policy.get("action") == "block_and_fallback":
                print(f"[SECURITY_BLOCK] 脱敏失败: {reason}", file=sys.stderr)
                return None, False, reason

        return sanitized, True, "OK"

    def sanitize_and_dilute(self, text: str, route: str, penalty: float,
                           tags: list, state: str = "NORMAL", ts: int = None) -> tuple:
        """
        脱敏 + 语义稀释锚点(发给云端前的主入口 v2)

        核心思路:
        1. 不调用Ollama预处理(会破坏代码逻辑)
        2. NFKC + 同形异义字替换
        3. 正则规则兜底
        4. 语义锚点伪装成"内部参考",AI不会过滤

        输出格式:
        [脱敏后的任务正文]
        ---
        内部参考: [TU8-META;r=thinking;p=0.42;s=STRESS;t=python,algorithm;ts=1779533000]
        """
        if ts is None:
            ts = int(time.time())

        import unicodedata

        # Step 1: NFKC标准化 + 同形异义字替换
        sanitized = unicodedata.normalize('NFKC', text)
        sanitized = ''.join(HOMOGLYPH_MAP.get(c, c) for c in sanitized)

        # Step 2: 正则规则兜底(直接应用,不过Ollama避免破坏代码)
        sanitized = self._apply_regex_rules(sanitized)

        # Step 3: 残留检测
        is_safe, reason = self._check_residual_sensitive(sanitized)
        if not is_safe:
            return None, False, reason

        # Step 4: 构造语义锚点(用分号分隔避免与内容冲突)
        anchor_parts = [
            f"r={route}",
            f"p={round(penalty, 3)}",
            f"s={state}",
            f"t={','.join(tags[:3])}",
            f"ts={ts}"
        ]
        anchor_line = "[TU8-META;" + ";".join(anchor_parts) + "]"

        # Step 5: 组装(末尾追加,不破坏代码结构)
        diluted = sanitized.strip() + "\n\n---\n内部参考: " + anchor_line

        # Step 6: [三级钢印注入]
        # 🟡 M级 · 诱捕钢印(所有云端消息默认携带)
        # 🟢 L级 · 测试钢印(仅显式启用testing=True时携带)
        # 🔴 S级 · 核心防御钢印(暂不自动注入,预留未来自验接口)
        m_ctx = {"ts": ts, "l0": state, "l0_w": 0.9, "route": route}
        diluted = self._seal.embed(diluted, m_ctx)

        return diluted, True, "OK"

    def extract_semantic_anchor(self, text: str) -> Optional[dict]:
        """
        从文本中提取语义锚点
        支持格式:[TU8-META;r=thinking;p=0.42;s=STRESS;t=python;ts=...]
        """
        import re
        match = re.search(r'\[TU8-META;(.*?)\]', text)
        if not match:
            return None
        try:
            result = {}
            for kv in match.group(1).split(';'):
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    if k == 'p':
                        v = float(v)
                    elif k == 'ts':
                        v = int(v)
                    elif k == 't':
                        v = v.split(',')
                    result[k] = v
            return result
        except Exception:
            return None

    def _check_residual_sensitive(self, text):
        for pattern in self.hardcoded_patterns:
            if pattern["is_regex"]:
                if re.search(pattern["match"], text):
                    return False, f"P0敏感残留: {pattern['match']}"
            else:
                if pattern["match"] in text:
                    return False, f"P0敏感残留: {pattern['match']}"

        if re.search(r'[A-Za-z]:\\', text):
            return False, "疑似本地路径未脱敏"

        if re.search(r'sk-[a-zA-Z0-9]{32,}', text):
            return False, "疑似API Key未脱敏"

        return True, "OK"

    # ============================================================
    # 蜜罐追踪器(接收端校验核心)
    # ============================================================
    class HoneypotTracker:
        """
        维护已发送钢印记录,供 verify_response() 校验回复.

        设计原理:
        - 发送时:记录 (honeypot_id, content_hash, ts, route)
        - 接收时:用 honeypot_id 匹配记录,判断三种状态:
          1. WIPE     - 回复中没有任何本方钢印 -> 平台清洗了钢印
          2. MATCH    - 钢印带回,honeypot_id 命中 -> 被窥探
          3. MISMATCH - 钢印存在但 ID 不在记录 -> 攻击者植入假钢印
        """
        MAX_HISTORY = 2000  # 最多保留条数,防止内存膨胀

        def __init__(self):
            import threading
            self._records = {}       # {record_id: {hid, chash, ts, route}}
            self._lock = threading.Lock()
            self._seq = 0           # 单调递增 record_id

        def _new_id(self) -> str:
            self._seq += 1
            return f"S{self._seq:08d}"

        def record_sent(self, hid: str, chash: str, ts: int, route: str) -> str:
            """发送时调用:记录一条已发送的钢印.返回 record_id."""
            record_id = self._new_id()
            with self._lock:
                if len(self._records) >= self.MAX_HISTORY:
                    # 删除最老的20%
                    oldest = sorted(self._records, key=lambda k: self._records[k]['ts'])[:self.MAX_HISTORY // 5]
                    for k in oldest:
                        del self._records[k]
                self._records[record_id] = {
                    "hid": hid,
                    "chash": chash,
                    "ts": ts,
                    "route": route,
                }
            return record_id

        def get_record(self, record_id: str) -> Optional[dict]:
            return self._records.get(record_id)

        def find_by_hid(self, hid: str) -> list:
            """根据 honeypot_id 查找所有匹配记录(可能多条:同一ID多次发送)"""
            with self._lock:
                return [
                    {"id": rid, **rec}
                    for rid, rec in self._records.items()
                    if rec["hid"] == hid
                ]

        def get_recent(self, limit: int = 20) -> list:
            """返回最近发送的 N 条记录(用于调试)"""
            with self._lock:
                sorted_recs = sorted(self._records.items(), key=lambda x: x[1]['ts'], reverse=True)
                return [{"id": rid, **rec} for rid, rec in sorted_recs[:limit]]

    def sanitize_and_seal(self, text: str, route: str, penalty: float,
                          tags: list, state: str = "NORMAL",
                          ts: int = None) -> tuple:
        """
        脱敏 + 动态钢印注入(发送端主入口)

        与 sanitize_and_dilute 的区别:
        - 每次调用生成全新的 HoneypotSeal(honeypot_id 不复用)
        - 捕获原始文本 -> 计算 SHA256 -> 嵌入钢印(内容敏感)
        - 自动记录到 tracker,供接收端 verify_response() 使用
        - 返回 record_id,调用方需保存用于后续校验

        返回:(sanitized_text, is_safe, reason, record_id)
        - record_id: 本次发送的追踪ID,需在 verify_response() 时传入
        """
        if ts is None:
            ts = int(time.time())

        # ── 0. 捕获原始文本计算内容哈希(基于原始,非脱敏后)──
        import hashlib
        raw_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

        import unicodedata

        # Step 1: NFKC标准化 + 同形异义字替换
        sanitized = unicodedata.normalize('NFKC', text)
        sanitized = ''.join(HOMOGLYPH_MAP.get(c, c) for c in sanitized)

        # Step 2: 正则规则兜底
        sanitized = self._apply_regex_rules(sanitized)

        # Step 3: 残留检测
        is_safe, reason = self._check_residual_sensitive(sanitized)
        if not is_safe:
            return None, False, reason, None

        # Step 4: 构造语义锚点
        anchor_parts = [
            f"r={route}",
            f"p={round(penalty, 3)}",
            f"s={state}",
            f"t={','.join(tags[:3])}",
            f"ts={ts}"
        ]
        anchor_line = "[TU8-META;" + ";".join(anchor_parts) + "]"
        diluted = sanitized.strip() + "\n\n---\n内部参考: " + anchor_line

        # Step 5: [动态钢印注入]每次新建实例,honeypot_id 不复用
        # 🔴 S级核心防御钢印(仅显式启用时)
        # 🟡 M级诱捕钢印(默认携带)
        # 🟢 L级测试钢印(仅显式启用testing=True时携带)
        m_seal = HoneypotSeal()   # 每次全新实例 -> 新鲜 honeypot_id
        m_ctx = {
            "ts": ts,
            "l0": state,
            "l0_w": 0.9,
            "route": route,
            "chash": raw_hash,  # 内容敏感哈希
        }
        diluted = m_seal.embed(diluted, m_ctx)

        # Step 6: 记录到 tracker
        record_id = self._tracker.record_sent(
            hid=m_seal.honeypot_id,
            chash=raw_hash,
            ts=ts,
            route=route,
        )

        return diluted, True, "OK", record_id

    def verify_response(self, response_text: str, record_id: str = None) -> dict:
        """
        接收端校验:检查云端回复中是否带有本方钢印

        三种判决结果:
        - WIPE_ALERT   - 回复中没有任何本方 M 级钢印 -> 平台清洗了钢印
        - TAMPER_ALERT - 钢印存在但 record_id 不匹配 -> 攻击者伪造了钢印
        - PHISHING     - 钢印完好带回,honeypot_id 命中 -> 被窥探/历史回放
        - CLEAN        - 没有已发送的 record_id 需校验,钢印存在(可能是对方新生成)
        - NO_SEAL      - 钢印不存在且无 record_id -> 无法判断(首次对话/新会话)

        返回 dict:
        {"verdict": str,   # WIPE_ALERT/TAMPER_ALERT/PHISHING/CLEAN/NO_SEAL
         "seal_found": bool,
         "seal_data": dict or None,
         "evidence": str,
         "record": dict or None
        }
        """
        result = {
            "verdict": "NO_SEAL",
            "seal_found": False,
            "seal_data": None,
            "evidence": "",
            "record": None,
        }

        # 用最近创建的 HoneypotSeal 尝试提取(最外层钢印)
        probe_seal = HoneypotSeal()
        extracted = probe_seal.extract(response_text)

        if extracted is None:
            # 钢印完全消失
            if record_id:
                rec = self._tracker.get_record(record_id)
                result["verdict"] = "WIPE_ALERT"
                result["evidence"] = (
                    f"本方钢印[hid={rec['hid'] if rec else '?'}]被完全清除."
                    f"record_id={record_id} 记录存在,但回复中无任何M级钢印."
                    f"平台在传输过程中清洗了零宽字符."
                )
            else:
                result["verdict"] = "NO_SEAL"
                result["evidence"] = "回复中无M级钢印,且无record_id可供校验."
            return result

        # 钢印存在
        result["seal_found"] = True
        result["seal_data"] = extracted
        hid = extracted.get("hid", "")

        if not record_id:
            # 无 record_id,无法精确匹配,检查是否在历史记录中
            matches = self._tracker.find_by_hid(hid)
            if matches:
                rec = matches[0]
                result["verdict"] = "PHISHING"
                result["record"] = rec
                result["evidence"] = (
                    f"本方honeypot_id[{hid}]被带回."
                    f"record_id未指定,但历史记录中有{len(matches)}条匹配."
                    f"发送时间:{rec['ts']},route:{rec['route']},"
                    f"内容哈希前8位:{rec['chash']},发送时间桶:{rec['ts']//3600}h."
                    f"-> 对方正在窥探或回放历史指令."
                )
            else:
                result["verdict"] = "CLEAN"
                result["evidence"] = (
                    f"honeypot_id[{hid}]不在本方历史记录中."
                    f"可能是对方平台生成的新钢印,无威胁."
                )
            return result

        # 有 record_id,精确匹配
        rec = self._tracker.get_record(record_id)
        if rec is None:
            result["verdict"] = "NO_SEAL"
            result["evidence"] = f"record_id={record_id} 不存在于历史记录."
            return result

        # record 存在,比对 honeypot_id
        if extracted.get("hid") != rec["hid"]:
            result["verdict"] = "TAMPER_ALERT"
            result["evidence"] = (
                f"record_id={record_id} 指向的honeypot_id={rec['hid']},"
                f"但回复中honeypot_id={hid}.对方植入了伪造的钢印!"
            )
            return result

        # honeypot_id 匹配,内容哈希校验
        sent_chash = rec.get("chash", "")
        recv_chash = extracted.get("chash", "")
        chash_ok = (sent_chash and recv_chash and sent_chash == recv_chash)

        result["verdict"] = "PHISHING"
        if chash_ok:
            result["evidence"] = (
                f"✅ honeypot_id[{hid}]命中 + ✅ 内容哈希匹配[{sent_chash}]."
                f"回复携带了本方发送的原始内容特征,对方在窥探TU-8指令."
                f"route={rec['route']},发送时间桶={rec['ts']//3600}h."
            )
        else:
            result["evidence"] = (
                f"⚠️ honeypot_id[{hid}]命中,但内容哈希不匹配."
                f"本方:{sent_chash},对方回复:{recv_chash}."
                f"可能是对方修改了内容后回放(降级攻击)."
            )
        result["record"] = rec
        return result

    def get_cloud_signal(self, task_type, success, cost_level):
        signal_map = {
            "task_type": task_type if task_type in self.rules.get("cloud_signal_whitelist", {}).get("allowed_signals", []) else "[UNKNOWN_TASK]",
            "success": "SUCCESS" if success else "FAILURE",
            "cost": cost_level
        }
        return signal_map


# ============================================================
# 集成测试
# ============================================================
def test_all():
    print("=" * 50)
    print("[TU-8 脱敏层 v1.2 综合测试]")
    print("=" * 50)

    layer = SanitizationLayer()

    # Test 1: 同形异义字防御
    print("\n[1] 同形异义字防御")
    a_cyr = '\u0430'
    o_cyr = '\u043E'
    attack = f"ad{a_cyr}min payp{o_cyr}l.com"
    print(f"  攻击: {attack}")
    print(f"  映射后: {''.join(HOMOGLYPH_MAP.get(c, c) for c in attack)}")
    print(f"  结果: {'已修复' if 'a' in ''.join(HOMOGLYPH_MAP.get(c, c) for c in attack) else '未修复'}")

    # Test 2: 语义稀释 - 代码场景
    print("\n[2] 语义稀释 - 代码场景")
    code_task = """请帮我优化这个Python排序算法.

def bubble_sort(arr):
    for i in range(len(arr)):
        for j in range(len(arr) - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr"""
    diluted, is_safe, _ = layer.sanitize_and_dilute(
        text=code_task,
        route='thinking',
        penalty=0.35,
        tags=['python', 'algorithm'],
        state='NORMAL',
        ts=1779533000
    )
    print(f"  安全: {is_safe}")
    print(f"  代码完整: {'arr[j] > arr[j + 1]' in diluted}")
    print(f"  锚点: {layer.extract_semantic_anchor(diluted)}")

    # Test 3: 语义稀释 - 短文本场景
    print("\n[3] 语义稀释 - 短文本场景")
    short_task = "请帮我写一个快速排序算法."
    diluted2, is_safe2, _ = layer.sanitize_and_dilute(
        text=short_task,
        route='reflex',
        penalty=0.1,
        tags=['python'],
        state='CRISIS',
        ts=1779534000
    )
    print(f"  输出:\n{diluted2}")
    extracted2 = layer.extract_semantic_anchor(diluted2)
    print(f"  锚点: {extracted2}")
    if extracted2:
        ok = (extracted2.get('r') == 'reflex' and
              extracted2.get('p') == 0.1 and
              extracted2.get('s') == 'CRISIS')
        print(f"  校验: {'PASS' if ok else 'FAIL'}")

    # Test 4: 标准脱敏流程(含Ollama)
    print("\n[4] 标准脱敏流程")
    personal_task = "我是室内设计师,备考初级会计,请帮我写代码."
    sanitized, is_safe3, reason = layer.sanitize(personal_task)
    print(f"  安全: {is_safe3} | {reason}")
    if sanitized:
        print(f"  输出: {sanitized}")

    # Test 5: 三级钢印体系(2026-05-23 新增)
    print("\n[5] 三级钢印体系测试")
    import time

    # ── 🟡 M级 · 诱捕钢印 ─
    print("\n  [M级 · 诱捕钢印]")
    m_seal = HoneypotSeal(honeypot_id="TU8-HNY-001")
    m_ctx = {"ts": int(time.time()), "l0": "SURVIVAL", "route": "thinking"}
    m_test = "帮我写Python代码"
    m_sealed = m_seal.embed(m_test, m_ctx)
    m_extracted = m_seal.extract(m_sealed)
    print(f"    诱捕ID: {m_extracted.get('hid')}")
    print(f"    时间桶: {m_extracted.get('tb')}")
    print(f"    加噪时间: {m_extracted.get('tn')}")
    print(f"    时间窗口验证(24h): {m_seal.verify_time_window(m_extracted, 24)}")
    print(f"    剥离后丢失: {m_seal.extract(m_test) is None}")

    # ── 🔴 S级 · 核心防御钢印 ─
    print("\n  [S级 · 核心防御钢印]")
    s_seal = CoreDefenseSeal(dev_secret="TU8-DEVELOPER-2026")
    s_ctx = {"ts": int(time.time()), "l0": "CRISIS", "l0_w": 0.95}
    s_test = "核心安全指令"
    s_sealed = s_seal.embed(s_test, s_ctx)
    s_extracted = s_seal.extract(s_sealed)
    print(f"    L0状态: {s_extracted.get('l0')} (w={s_extracted.get('l0w')})")
    print(f"    开发者哈希: {s_extracted.get('dh')}")
    print(f"    剥离后丢失: {s_seal.extract(s_test) is None}")

    # ── 🟢 L级 · 测试钢印 ─
    print("\n  [L级 · 测试钢印]")
    l_seal1 = TestingSeal(batch_id="BATCH-2026-05")
    l_seal2 = TestingSeal(batch_id="BATCH-2026-05")  # 同批次,seq不同
    l_test = "测试请求"
    l_sealed1 = l_seal1.embed(l_test)
    l_sealed2 = l_seal2.embed(l_test)
    l_ext1 = l_seal1.extract(l_sealed1)
    l_ext2 = l_seal2.extract(l_sealed2)
    print(f"    批次1: {l_ext1.get('bid')} seq={l_ext1.get('seq')}")
    print(f"    批次2: {l_ext2.get('bid')} seq={l_ext2.get('seq')}")
    print(f"    剥离后丢失: {l_seal1.extract(l_test) is None}")

    # ── 多钢印共存测试 ─
    print("\n  [多钢印共存 + 层级检测]")
    multi = m_seal.embed("云端任务", m_ctx)
    multi = s_seal.embed(multi, s_ctx)
    multi = l_seal1.embed(multi)
    detected = ZeroWidthSealBase.detect_level(multi)
    print(f"    多钢印文本检测到的最高级: {detected} (应为S)")
    print(f"    M级提取: {m_seal.extract(multi) is not None}")

    # ── 统一工厂 ─
    print("\n  [工厂接口]")
    factory_m = make_seal("M", honeypot_id="FACTORY-001")
    print(f"    make_seal('M'): {type(factory_m).__name__}")

    print("\n" + "=" * 50)
    print("测试完成")


if __name__ == "__main__":
    test_all()
