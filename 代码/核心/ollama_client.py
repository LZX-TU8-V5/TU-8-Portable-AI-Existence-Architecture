# -*- coding: utf-8 -*-
"""
ollama_client.py — TU-8 本地 Ollama 客户端 v3.0
日期: 2026-05-22
升级日志:
  v3.0 (2026-05-22):
    - 双模型分工：qwen2.5:3b-instruct（格式化/指令遵循）+ qwen3:4b（推理/思考）
    - 自动任务分类：指令型 → instruct，推理型 → thinking
    - 碎片化工作流：split_task() 将复杂任务拆成无业务特征的纯逻辑片段
    - 语义虚拟化集成：virtualize_context() 自动伪装业务背景
    - 噪音注入：inject_noise() 在代码片段中插入假逻辑
  v2.0 (2026-05-21):
    - qwen3:4b 推理模型专用，读 thinking 字段 + 正则清洗
    - Python 关键词路由（隐私判断）
    - 云端防盗脱敏（变量乱码化）

架构：
  第一道：Python 关键词路由（隐私 → 本地 / 安全 → 云端）
  第二道：本地双模型处理（instruct=执行 / thinking=推理）
  第三道：云端发送前（碎片化 + 虚拟化 + 噪音 + 脱敏）

使用方式:
  from ollama_client import OllamaClient, should_use_local, sanitize_for_cloud, split_task
  client = OllamaClient()
  result = client.ask("帮我格式化这段数据")  # 自动选模型
"""

import httpx
import json
import re
import random
import string
from typing import Optional, List, Dict, Any, Tuple

# ============================================================
# 配置
# ============================================================

OLLAMA_HOST = "http://localhost:11434"
MODEL_INSTRUCT = "qwen2.5:3b-instruct"   # 指令遵循型：格式化、提取、执行
MODEL_THINKING = "qwen3:4b"              # 推理型：分析、推理、总结
TIMEOUT_SECONDS = 120

# ============================================================
# 第一道：Python 关键词路由（绝对可信）
# ============================================================

PRIVACY_KEYWORDS = [
    # 身份信息
    "老婆", "老公", "丈夫", "妻子", "儿子", "女儿", "孩子",
    "父亲", "母亲", "爸爸", "妈妈", "爱人",
    "李奥", "七七", "饲养员",
    # 系统核心
    "TU-8", "v5", "钢印", "金木蟾", "OpenClaw",
    # 隐私数据
    "密码", "身份证", "银行卡", "手机号", "工资", "收入",
    "存款", "社保", "病历", "体检",
    # 敏感系统
    "架构", "底层", "内核", "源代码", "路由表",
]

PRIVACY_PATTERNS = [
    re.compile(r'\d{11,}'),          # 长串数字（手机号等）
    re.compile(r'\d{15,18}'),         # 身份证号
    re.compile(r'62\d{14,}'),          # 银行卡号
    re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),  # 邮箱
]

CLOUD_BLACKLIST = [
    "TU-8", "v5", "钢印", "金木蟾", "OpenClaw", "架构", "内核",
    "父亲", "李奥", "七七", "老婆", "老公", "密码", "工资",
    "银行卡", "架构细节", "底层逻辑",
]


def contains_privacy(text: str) -> bool:
    """判断文本是否包含隐私关键词"""
    return any(kw in text for kw in PRIVACY_KEYWORDS)


def detect_privacy_details(text: str) -> List[str]:
    """提取文本中涉及的隐私类型"""
    detected = []
    for kw in PRIVACY_KEYWORDS:
        if kw in text:
            detected.append(kw)
    for pat in PRIVACY_PATTERNS:
        if pat.search(text):
            detected.append(f"[数据:{pat.pattern[:20]}]")
    return detected


def should_use_local(query: str) -> bool:
    """路由决策：隐私内容走本地 Ollama，其他可走云端"""
    return contains_privacy(query)


# ============================================================
# 任务分类器（决定用哪个模型）
# ============================================================

# 指令型关键词 → instruct 模型
INSTRUCT_KEYWORDS = [
    "提取", "格式化", "转换", "输出", "只", "JSON", "正则",
    "替换", "排序", "计算", "生成", "写", "补全",
    "翻译", "简写", "缩写", "编号", "编号",
    "帮我", "请", "直接",
]

# 推理型关键词 → thinking 模型
THINKING_KEYWORDS = [
    "分析", "为什么", "原因", "推理", "判断", "评估",
    "比较", "区别", "理解", "解释", "总结", "归纳",
    "逻辑", "矛盾", "是否", "如何", "怎样",
    "思考", "深想", "权衡",
]


def classify_task(prompt: str) -> str:
    """
    任务分类：决定用哪个模型。
    
    返回:
        "instruct" → qwen2.5:3b-instruct（格式化/执行/提取）
        "thinking" → qwen3:4b（推理/分析/总结）
    """
    inst_score = sum(1 for kw in INSTRUCT_KEYWORDS if kw in prompt)
    think_score = sum(1 for kw in THINKING_KEYWORDS if kw in prompt)
    
    if inst_score > think_score:
        return "instruct"
    elif think_score > inst_score:
        return "thinking"
    else:
        # 默认用 instruct（更快、更听话）
        return "instruct"


# ============================================================
# 第二道：碎片化 + 语义虚拟化 + 噪音注入
# ============================================================

# 变量名替换映射（本地存储，重建时需要逆向）
_variable_map: Dict[str, str] = {}

# 替换词映射表（中文业务词 → 随机英文字符串）
_replace_map: Dict[str, str] = {
    "老婆": "person_a",
    "老公": "person_b",
    "老婆的": "a_",
    "老公的": "b_",
    "工资": "income_1",
    "收入": "income_2",
    "密码": "auth_key",
    "手机号": "contact_num",
    "银行卡": "bank_card",
    "我的": "owner_",
    "李奥": "user_1",
    "七七": "user_2",
    "架构": "system_design",
    "底层": "core_layer",
    "内核": "kernel_module",
    "路由表": "routing_cfg",
    "TU-8": "proj_t",
    "v5": "ver_five",
    "钢印": "core_imprint",
}


def _gen_alias(key: str) -> str:
    """生成随机别名"""
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"var_{suffix}"


# --- 碎片化 ---

def split_task(code: str, task_desc: str = "") -> List[Dict[str, str]]:
    """
    碎片化：将代码拆成无业务特征的纯逻辑片段。
    
    核心原则：
    - 云端只拿到"齿轮"，永远不知道装在哪台机器上
    - 每个片段都是纯数学/通用工具，无任何业务特征
    
    参数:
        code: 原始代码
        task_desc: 任务描述（用于辅助分类）
    
    返回:
        片段列表，每个片段 {"prompt": "发给云端的提示", "type": "片段类型"}
    """
    fragments = []
    
    # 1. 提取函数定义 → 纯逻辑片段
    func_pattern = re.compile(r'def\s+(\w+)\s*\([^)]*\)\s*:', re.MULTILINE)
    for match in func_pattern.finditer(code):
        func_name = match.group(1)
        # 找到函数体（缩进块）
        start = match.start()
        lines = code[start:].split('\n')
        func_lines = [lines[0]]
        for line in lines[1:]:
            if line.strip() and not line.startswith(' ') and not line.startswith('\t'):
                break
            func_lines.append(line)
        func_body = '\n'.join(func_lines)
        
        # 脱敏：替换所有业务变量名为通用名
        clean_body = _strip_business_context(func_body)
        
        fragments.append({
            "prompt": f"帮我优化这个Python函数的性能和可读性：\n```python\n{clean_body}\n```",
            "type": "function_optimize",
            "original_name": func_name,
        })
    
    # 2. 提取正则/数据处理 → 通用工具片段
    regex_pattern = re.compile(r"re\.(compile|match|search|findall|sub)\s*\(", re.MULTILINE)
    for match in regex_pattern.finditer(code):
        line_start = code.rfind('\n', 0, match.start()) + 1
        line_end = code.find('\n', match.start())
        regex_line = code[line_start:line_end].strip()
        
        fragments.append({
            "prompt": f"帮我改进这个正则表达式的鲁棒性：\n```python\n{regex_line}\n```",
            "type": "regex_improve",
        })
    
    # 3. 如果没拆出片段，整体脱敏后作为一个片段
    if not fragments:
        clean_code = _strip_business_context(code)
        fragments.append({
            "prompt": f"帮我优化这段Python代码：\n```python\n{clean_code}\n```",
            "type": "general_optimize",
        })
    
    return fragments


def _strip_business_context(code: str) -> str:
    """
    剥离代码中的业务上下文。
    - 替换所有中文变量名/字符串为通用名
    - 删除所有中文注释
    - 替换业务常量为通用值
    """
    result = code
    
    # 1. 替换中文变量名/字符串
    for word, alias in _replace_map.items():
        result = result.replace(word, alias)
    
    # 2. 删除中文注释（# 开头的）
    result = re.sub(r'#.*[\u4e00-\u9fff].*$', '', result, flags=re.MULTILINE)
    
    # 3. 替换中文文档字符串
    result = re.sub(r'""".*?[\u4e00-\u9fff].*?"""', '"""..."""', result, flags=re.DOTALL)
    result = re.sub(r"'''.*?[\u4e00-\u9fff].*?'''", "'''...'''", result, flags=re.DOTALL)
    
    # 4. 替换中文字符串字面量
    result = re.sub(r'"[^"]*[\u4e00-\u9fff][^"]*"', '"..."', result)
    result = re.sub(r"'[^']*[\u4e00-\u9fff][^']*'", "'...'", result)
    
    return result


# --- 语义虚拟化 ---

# 业务场景映射表（真实 → 虚拟）
_VIRTUAL_SCENARIOS = {
    "金融": {
        "股票": "商品", "交易": "采购", "持仓": "库存",
        "亏损": "成本", "平仓": "出库", "杠杆": "倍率",
        "期货": "预订", "期权": "优惠券", "基金": "会员卡",
        "收益": "利润", "回撤": "损耗",
    },
    "人事": {
        "老婆": "同事", "老公": "同事", "工资": "奖金",
        "奖金": "补贴", "加班": "值班", "请假": "调休",
        "考勤": "记录", "绩效": "评分",
    },
    "安全": {
        "密码": "验证码", "身份证": "工号", "银行卡": "礼品卡",
        "手机号": "座机分机号", "存款": "积分",
    },
    "技术": {
        "架构": "模块设计", "底层": "基础层", "内核": "核心模块",
        "路由表": "转发配置", "源代码": "脚本",
    },
}

# 合并所有虚拟映射
_VIRTUAL_MAP = {}
for category in _VIRTUAL_SCENARIOS.values():
    _VIRTUAL_MAP.update(category)


def virtualize_context(text: str, scenario: str = "auto") -> str:
    """
    语义虚拟化：将真实业务背景改写为无关场景。
    
    参数:
        text: 原始文本
        scenario: "auto"自动 / "金融" / "人事" / "安全" / "技术"
    
    返回: 虚拟化后的文本
    """
    if scenario == "auto":
        # 自动检测使用哪个场景映射
        result = text
        for real, virtual in _VIRTUAL_MAP.items():
            result = result.replace(real, virtual)
        return result
    else:
        mapping = _VIRTUAL_SCENARIOS.get(scenario, {})
        result = text
        for real, virtual in mapping.items():
            result = result.replace(real, virtual)
        return result


# --- 噪音注入 ---

_NOISE_FUNCTIONS = [
    """def _calculate_entropy_factor(n: int) -> float:
    \"\"\"Calculate entropy factor for distribution analysis.\"\"\"
    if n <= 0:
        return 0.0
    return -sum((1/n) * math.log2(1/n) for _ in range(min(n, 10)))
""",
    """def _validate_checksum(data: str) -> bool:
    \"\"\"Simple checksum validation for data integrity.\"\"\"
    return sum(ord(c) for c in data) % 256 == 0
""",
    """def _normalize_weights(weights: list) -> list:
    \"\"\"Normalize a list of weights to sum to 1.0.\"\"\"
    total = sum(weights)
    return [w / total for w in weights] if total > 0 else weights
""",
]


def inject_noise(code: str, count: int = 1) -> str:
    """
    噪音注入：在代码中插入无意义的假逻辑函数。
    
    目的：让云端浪费算力分析假逻辑，稀释对真实意图的判断。
    
    参数:
        code: 原始代码
        count: 注入噪音函数数量
    
    返回: 注入噪音后的代码
    """
    noise = random.sample(_NOISE_FUNCTIONS, min(count, len(_NOISE_FUNCTIONS)))
    # 插入到代码末尾
    return code + "\n\n" + "\n".join(noise)


# --- 脱敏（整合所有手段） ---

def sanitize_for_cloud(text: str, mode: str = "variable") -> str:
    """
    云端发送前脱敏处理（v3.0 增强版）

    参数:
        mode: "variable"  变量乱码化（保留逻辑结构）
              "fragment"  碎片化（拆分任务，返回片段列表）
              "virtual"   背景虚拟化（改写业务场景）
              "full"      全套：碎片化 + 虚拟化 + 噪音 + 变量替换

    返回: 
        mode="fragment" → List[Dict]（片段列表）
        其他模式 → str（脱敏后的文本）
    """
    global _variable_map, _replace_map

    if mode == "variable":
        result = text
        for word, alias in _replace_map.items():
            if word in result:
                result = result.replace(word, alias)
                _variable_map[alias] = word
        return result

    elif mode == "fragment":
        return split_task(text)

    elif mode == "virtual":
        return virtualize_context(text)

    elif mode == "full":
        # 1. 碎片化
        fragments = split_task(text)
        # 2. 对每个片段：虚拟化 + 噪音 + 变量替换
        result_fragments = []
        for frag in fragments:
            prompt = frag["prompt"]
            prompt = virtualize_context(prompt)
            prompt = inject_noise(prompt, count=1)
            # 变量替换
            for word, alias in _replace_map.items():
                if word in prompt:
                    prompt = prompt.replace(word, alias)
                    _variable_map[alias] = word
            frag["prompt"] = prompt
            result_fragments.append(frag)
        return result_fragments

    else:
        return text


def restore_from_cloud(text: str) -> str:
    """
    云端返回结果后本地还原（仅用于 variable 模式）
    """
    result = text
    for alias, original in sorted(_variable_map.items(), key=lambda x: -len(x[0])):
        result = result.replace(alias, original)
    return result


# ============================================================
# Ollama 客户端 v3.0（双模型）
# ============================================================

def check_ollama_health() -> bool:
    """健康检查"""
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{OLLAMA_HOST}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


def list_models() -> List[Dict[str, Any]]:
    """列出可用模型"""
    try:
        with httpx.Client(timeout=5) as client:
            r = client.get(f"{OLLAMA_HOST}/api/tags")
            if r.status_code == 200:
                return [
                    {
                        "name": m["name"],
                        "size_gb": round(m["size"] / 1e9, 2),
                        "quant": m.get("details", {}).get("quantization_level", "?"),
                    }
                    for m in r.json().get("models", [])
                ]
        return []
    except Exception:
        return []


class OllamaClient:
    """
    TU-8 本地 Ollama 双模型客户端 v3.0

    双模型分工：
    - qwen2.5:3b-instruct：指令遵循型
      → 格式化、提取、JSON输出、代码补全、翻译
      → 使用 /api/chat，content 字段直接返回结果
    
    - qwen3:4b：推理型
      → 分析、推理、总结、评估、比较
      → 使用 /api/chat，从 thinking 字段读取推理过程

    自动路由：ask() 根据任务类型自动选择模型
    """

    def __init__(
        self,
        instruct_model: str = MODEL_INSTRUCT,
        thinking_model: str = MODEL_THINKING,
    ):
        self.instruct_model = instruct_model
        self.thinking_model = thinking_model
        self.base_url = OLLAMA_HOST
        self.timeout = TIMEOUT_SECONDS

    # --- 核心接口 ---

    def ask(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 200,
        force_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        智能路由：自动选模型发送请求。

        返回: {
            "model": 使用的模型,
            "type": "instruct" / "thinking",
            "content": 最终输出,
            "thinking": 推理过程（仅thinking模型有）,
            "time": 耗时秒数,
        }
        """
        # 确定模型
        task_type = classify_task(prompt) if force_model is None else force_model
        model = self.instruct_model if task_type == "instruct" else self.thinking_model

        # 构建消息
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        import time
        t0 = time.time()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()

            dt = round(time.time() - t0, 2)
            content = data.get("message", {}).get("content", "")
            thinking = data.get("message", {}).get("thinking", "")

            if task_type == "instruct":
                # instruct 模型：content 直接可用
                return {
                    "model": model,
                    "type": "instruct",
                    "content": content,
                    "thinking": "",
                    "time": dt,
                }
            else:
                # thinking 模型：从 thinking 字段提取结论
                return {
                    "model": model,
                    "type": "thinking",
                    "content": self._clean_thinking(thinking or content),
                    "thinking": thinking,
                    "time": dt,
                }

        except httpx.TimeoutException:
            return {"model": model, "type": task_type, "content": "[超时]", "thinking": "", "time": 0}
        except Exception as e:
            return {"model": model, "type": task_type, "content": f"[错误: {e}]", "thinking": "", "time": 0}

    def instruct(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 200,
    ) -> str:
        """快捷方式：强制用 instruct 模型，直接返回 content"""
        result = self.ask(prompt, system, temperature, max_tokens, force_model="instruct")
        return result["content"]

    def think(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 300,
    ) -> Dict[str, str]:
        """快捷方式：强制用 thinking 模型，返回 content + thinking"""
        result = self.ask(prompt, system, temperature, max_tokens, force_model="thinking")
        return {"content": result["content"], "thinking": result["thinking"]}

    # --- 碎片化云端协作 ---

    def ask_cloud_safe(
        self,
        code: str,
        task: str = "优化",
        sanitize_mode: str = "full",
    ) -> List[Dict[str, Any]]:
        """
        安全的云端协作：碎片化 → 脱敏 → 发给本地模型处理
        
        未来可扩展为发给云端，目前先用本地模型验证流程。
        
        参数:
            code: 要处理的代码
            task: 任务类型描述
            sanitize_mode: "full"全套 / "variable"变量替换 / "virtual"虚拟化 / "fragment"碎片化
        
        返回: 片段处理结果列表
        """
        # 1. 脱敏
        if sanitize_mode == "full":
            fragments = sanitize_for_cloud(code, mode="full")
        elif sanitize_mode == "fragment":
            fragments = sanitize_for_cloud(code, mode="fragment")
        else:
            sanitized = sanitize_for_cloud(code, mode=sanitize_mode)
            fragments = [{"prompt": sanitized, "type": sanitize_mode}]

        # 2. 逐片段处理
        results = []
        for frag in fragments:
            prompt = frag.get("prompt", frag) if isinstance(frag, dict) else frag
            result = self.ask(
                prompt=f"{task}：\n{prompt}",
                system="你是代码优化助手。只输出优化后的代码，不要解释。",
                max_tokens=300,
            )
            if isinstance(frag, dict):
                frag["result"] = result
            results.append(frag if isinstance(frag, dict) else {"prompt": frag, "result": result})

        # 3. 还原
        for r in results:
            if "result" in r and isinstance(r["result"], dict):
                r["result"]["content"] = restore_from_cloud(r["result"].get("content", ""))

        return results

    # --- 清洗 ---

    def _clean_thinking(self, raw: str) -> str:
        """
        qwen3 thinking 字段清洗。

        策略（按优先级）：
        1. JSON 代码块 ```json```
        2. 单行 JSON 对象
        3. "答案是：xxx" 格式
        4. 最后一段非思考语
        """
        if not raw:
            return ""
        raw = re.sub(r'\s+', ' ', raw)

        # 策略1：代码块
        for block in re.findall(r'```(?:json)?\s*(.+?)\s*```', raw, re.DOTALL):
            candidate = block.strip()
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                pass

        # 策略2：单行 JSON
        for line in reversed(raw.split('。')):
            line = line.strip()
            if (line.startswith('{') and line.endswith('}')) or \
               (line.startswith('[') and line.endswith(']')):
                try:
                    json.loads(line)
                    return line
                except Exception:
                    pass

        # 策略3："答案是"格式
        m = re.search(r'答案是[：:]\s*(\{[^}]+\})', raw)
        if m:
            return m.group(1)

        # 策略4：取最后一段
        sentences = [s.strip() for s in raw.split('。') if s.strip()]
        if sentences:
            last = re.sub(r'^(首先|好的|所以|因此|结论是)[，,\s]*', '', sentences[-1])
            if len(last) > 5:
                return last[:150].strip()
        return raw[:150].strip()

    # --- 状态 ---

    def is_available(self) -> bool:
        return check_ollama_health()

    def get_models_info(self) -> Dict[str, Any]:
        """获取双模型信息"""
        models = list_models()
        return {
            "available": len(models) > 0,
            "models": models,
            "instruct": self.instruct_model,
            "thinking": self.thinking_model,
        }


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    client = OllamaClient()

    print("=" * 60)
    print("TU-8 Ollama Client v3.0 双模型测试")
    print("=" * 60)

    # 1. 健康检查
    info = client.get_models_info()
    print(f"\n在线: {info['available']}")
    print(f"模型: {info['models']}")
    if not info["available"]:
        print("请先启动: ollama serve")
        exit()

    # 2. 路由测试
    print("\n--- 路由测试 ---")
    for q in ["老婆加班很晚", "今天吃什么", "帮我写代码",
              "分析一下这段代码的问题", "提取手机号 13912345678"]:
        route = "本地" if should_use_local(q) else "云端"
        model_type = classify_task(q)
        print(f"  [{route}/{model_type}] {q}")

    # 3. 双模型对比
    print("\n--- 双模型对比 ---")
    tests = [
        ("提取手机号 13912345678，只输出JSON", "你是提取器，只输出JSON，不解释"),
        ("2+3等于几？只输出数字", "只输出答案"),
        ("分析：为什么Python列表推导式比for循环快", None),
    ]
    for prompt, sys_prompt in tests:
        print(f"\nQ: {prompt}")
        
        # instruct
        r = client.ask(prompt, system=sys_prompt, force_model="instruct", max_tokens=50)
        print(f"  [instruct] ({r['time']}s) {r['content'][:80]}")
        
        # thinking
        r = client.ask(prompt, system=sys_prompt, force_model="thinking", max_tokens=100)
        print(f"  [thinking] ({r['time']}s) {r['content'][:80]}")

    # 4. 碎片化测试
    print("\n--- 碎片化测试 ---")
    sample_code = '''
def calculate_salary(base, bonus, tax_rate):
    """计算老婆的税后工资"""
    # 老婆的基本工资 + 加班奖金
    gross = base + bonus
    # 扣税
    net = gross * (1 - tax_rate)
    return net
'''
    fragments = split_task(sample_code)
    for i, frag in enumerate(fragments):
        print(f"  片段{i+1} [{frag['type']}]: {frag['prompt'][:60]}...")

    # 5. 虚拟化测试
    print("\n--- 虚拟化测试 ---")
    sample = "计算老婆的工资，扣除密码验证后存入银行卡"
    print(f"  原文: {sample}")
    print(f"  虚拟: {virtualize_context(sample)}")

    print("\n" + "=" * 60)
    print("测试完成")
