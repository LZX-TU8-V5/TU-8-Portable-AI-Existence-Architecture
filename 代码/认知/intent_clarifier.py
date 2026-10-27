"""
TU-8 L2 方法论：意图澄清模块 (Intent Clarifier)
版本：v2.0 | 2026-05-22

升级日志:
  v2.0 (2026-05-22):
    - 接入 ollama_client v3.0 双模型语义增强
    - assess_fuzziness(): 规则评估后，灰色地带(0.3~0.6)调thinking做语义评估
    - generate_3q(): thinking模型生成针对性追问，替代通用模板
    - 降级策略：Ollama不可用时回退纯规则，零损失
  v1.0 (2026-05-16):
    - 7项迹象规则评估模糊度
    - 通用三问模板 + MVP草稿生成

【核心定位】
阶段一：意图澄清与拆解（想清楚再动手）
对应人类高手的"拆解任务+明确MVP"能力。

【触发条件】
收到任务时，自动评估模糊度。
模糊度 ≥ 阈值 → 暂停执行，输出3个追问 + MVP草稿模板。
模糊度 < 阈值 → 直接执行（实干优先协议）。

【三问核心】
Q1. 成功标准是什么？（预期结果）
Q2. 边界在哪？（哪些不做？）
Q3. 风险预案？（哪里最容易卡壳？）

【MVP草稿模板】
收到澄清后，生成"60分版本"骨架，让用户确认后再深度执行。
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import sys
import json

# 动态导入 ollama_client（跨目录）
_ollama_client = None
_ollama_available = None  # None=未检测, True/False

def _get_ollama_client():
    """懒加载 ollama_client，避免启动时依赖"""
    global _ollama_client, _ollama_available
    if _ollama_available is not None:
        return _ollama_client if _ollama_available else None
    try:
        core_dir = Path(__file__).resolve().parent.parent / "核心"
        if str(core_dir) not in sys.path:
            sys.path.insert(0, str(core_dir))
        from ollama_client import OllamaClient, check_ollama_health
        if check_ollama_health():
            _ollama_client = OllamaClient()
            _ollama_available = True
        else:
            _ollama_available = False
    except Exception:
        _ollama_available = False
    return _ollama_client if _ollama_available else None

# AI增强开关与参数
AI_CLARIFY_ENABLED = True         # 总开关
AI_FUZZINESS_ENHANCE_MIN = 0.3    # 规则评估>=0.3时才调AI（太清晰的没必要）
AI_FUZZINESS_ENHANCE_MAX = 0.8    # 规则评估>=0.8时也不调AI（已极度模糊，直接追问）
AI_TIMEOUT_SECONDS = 20          # AI超时


# ============================================================
# 配置
# ============================================================

FUZZINESS_THRESHOLD = 0.6          # 模糊度 ≥ 0.6 → 触发三问
HISTORY_DIR = Path(__file__).parent / "_intent_history"

HISTORY_DIR.mkdir(exist_ok=True)


# ============================================================
# 模糊度评估
# ============================================================

def assess_fuzziness(task_text: str, use_ai: bool = True) -> dict:
    """
    评估任务文本的模糊度（0.0 ~ 1.0）
    v2.0: 规则评估 + AI语义增强
    
    流程：
    1. 规则评估（7项迹象，0ms）
    2. 灰色地带(0.3~0.8) → thinking模型语义评估
    3. 合并结果，AI有权重调整
    """
    score = 0.0
    clues = []

    # === 规则评估（保留v1.0全部逻辑） ===
    
    # 迹象1：没有明确的动作词
    action_words = ["写", "创建", "分析", "修改", "删除", "更新",
                    "建立", "完成", "输出", "生成", "读取", "运行",
                    "build", "write", "create", "analyze", "modify"]
    if not any(word in task_text for word in action_words):
        score += 0.15
        clues.append("[?] 无明确动作词")

    # 迹象2：没有文件路径或输出格式
    path_patterns = [r"[A-Z]:\\", r"/[a-zA-Z]", r"\.[a-z]{2,4}",
                      r"\.(md|txt|py|json|yaml|csv|png|jpg|html|css|js)"]
    if not any(re.search(p, task_text) for p in path_patterns):
        score += 0.10
        clues.append("[?] 无文件路径/格式")

    # 迹象3：没有范围限定
    scope_words = ["哪些", "什么", "多少", "何时", "哪些",
                   "who|what|where|when|how|which"]
    if not any(word in task_text.lower() for word in scope_words):
        score += 0.15
        clues.append("[?] 无范围限定")

    # 迹象4：任务长度异常
    char_count = len(task_text.strip())
    if char_count < 10:
        score += 0.25
        clues.append("ERR 任务太短(<10字)")
    elif char_count > 500:
        score += 0.10
        clues.append("[~] 任务太长，可能含干扰")

    # 迹象5：问号过多
    question_count = task_text.count("?") + task_text.count("？")
    if question_count >= 3:
        score += 0.20
        clues.append("[?] 问号>=3，探索性问题")

    # 迹象6：包含模糊词
    vague_words = ["大概", "差不多", "随便", "随意", "看看",
                   "somehow", "maybe", "roughly", "sort of"]
    if any(word in task_text for word in vague_words):
        score += 0.10
        clues.append("[~] 含模糊修饰词")

    # 迹象7：没有成功标准描述
    success_words = ["完成", "搞定", "达到", "输出", "生成",
                     "done", "finish", "output", "produce", "finish"]
    if not any(word in task_text for word in success_words):
        score += 0.05
        clues.append("[~] 无成功标准描述")

    score = min(score, 1.0)
    
    # === AI语义增强 ===
    # 只在灰色地带调用AI（太清晰没必要，太模糊直接追问）
    ai_adjusted = False
    if use_ai and AI_CLARIFY_ENABLED and AI_FUZZINESS_ENHANCE_MIN <= score <= AI_FUZZINESS_ENHANCE_MAX:
        ai_result = _ai_assess_fuzziness(task_text, score)
        if ai_result is not None:
            ai_score, ai_clues = ai_result
            # AI权重：0.4（规则0.6 + AI0.4）
            score = score * 0.6 + ai_score * 0.4
            if ai_clues:
                clues.extend(ai_clues)
            ai_adjusted = True
    
    score = min(score, 1.0)
    return {
        "score": score,
        "level": "清晰" if score < 0.3 else
                "微模糊" if score < 0.6 else
                "模糊" if score < 0.8 else "极度模糊",
        "clues": clues,
        "ai_enhanced": ai_adjusted,
    }


def _ai_assess_fuzziness(task_text: str, rule_score: float) -> Optional[Tuple[float, List[str]]]:
    """
    AI语义模糊度评估（instruct模型 — 分类任务优先用instruct）
    
    返回: None=AI不可用, (score, clues)=评估结果
    """
    client = _get_ollama_client()
    if client is None:
        return None
    
    prompt = (
        f"评估以下任务的模糊度(0.0~1.0)，1.0=完全模糊，0.0=完全清晰。\n"
        f"任务：\"{task_text}\"\n"
        f"规则评估分数：{rule_score:.2f}\n"
        f"请分析：1)用户真正想做什么 2)缺少哪些关键信息 3)可能的理解歧义\n"
        f"输出严格JSON格式，字段：score(浮点), missing_info(字符串数组), ambiguity(字符串)\n"
        f"不要输出任何解释，只输出JSON。"
    )
    
    try:
        result = client.ask(
            prompt=prompt,
            system="你是任务模糊度评估专家。只输出JSON。",
            force_model="instruct",
            temperature=0.1,
            max_tokens=150,
        )
        content = result.get("content", "")
        
        # 解析JSON - 取最后一个JSON匹配（防鹦鹉学舌）
        content = content.strip()
        json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        if not json_matches:
            # 简单fallback
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            json_matches = [json_match.group()] if json_match else []
        if not json_matches:
            return None
        
        # 尝试每个匹配，从最后一个开始（最新=真正答案）
        for json_str in reversed(json_matches):
            try:
                parsed = json.loads(json_str)
                ai_score = float(parsed.get("score", rule_score))
                ai_score = max(0.0, min(1.0, ai_score))
                
                # 跳过鹦鹉分数（与rule_score完全相同=可能是示例）
                if abs(ai_score - rule_score) < 0.01 and not parsed.get("missing_info"):
                    continue
                
                ai_clues = []
                if parsed.get("missing_info"):
                    missing = parsed["missing_info"][:3]
                    ai_clues.append(f"[AI] 缺少信息：{'、'.join(missing)}")
                if parsed.get("ambiguity"):
                    ai_clues.append(f"[AI] 歧义：{parsed['ambiguity'][:50]}")
                
                return (ai_score, ai_clues)
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
        
        return None
    
    except (json.JSONDecodeError, ValueError, Exception):
        return None


# ============================================================
# 三问生成
# ============================================================

def generate_3q(task_text: str, use_ai: bool = True) -> str:
    """
    根据任务文本生成3个追问（v2.0 AI增强版）
    
    策略：
    - AI可用 → thinking模型生成针对性追问
    - AI不可用 → 回退通用模板（v1.0逻辑）
    """
    if use_ai and AI_CLARIFY_ENABLED:
        ai_questions = _ai_generate_3q(task_text)
        if ai_questions:
            return ai_questions
    
    # 降级：通用模板
    q1 = "**Q1. 成功标准是什么？**\n"
    q1 += '   我要交付什么才算「完成」？\n'
    q1 += "   （例：写一个能运行的脚本 / 输出一份分析报告 / 创建X个文件）"

    q2 = "**Q2. 边界在哪？**\n"
    q2 += "   这个任务**不包括**哪些内容？\n"
    q2 += "   （例：不用处理错误情况 / 不需要美化界面 / 只做初稿）"

    q3 = "**Q3. 风险预案？**\n"
    q3 += "   你觉得哪里最容易卡壳？\n"
    q3 += "   （例：数据找不到 / 权限不够 / 格式不清楚）"

    return f"{q1}\n\n{q2}\n\n{q3}"


def _ai_generate_3q(task_text: str) -> Optional[str]:
    """
    AI生成针对性三问（thinking模型 — 需要创造性推理）
    
    返回: None=AI不可用, str=格式化的三问文本
    """
    client = _get_ollama_client()
    if client is None:
        return None
    
    prompt = (
        f"用户提出了一个模糊的任务，请生成3个精准的追问来帮助澄清。\n"
        f"任务：\"{task_text}\"\n"
        f"\n"
        f"要求：\n"
        f"1. Q1针对成功标准（交付什么算完成）\n"
        f"2. Q2针对边界（哪些不做）\n"
        f"3. Q3针对风险（哪里容易卡壳）\n"
        f"4. 追问要具体到这个任务，不要通用模板\n"
        f"\n"
        f"输出严格JSON格式，字段：q1(字符串), q2(字符串), q3(字符串)\n"
        f"不要输出任何解释，只输出JSON。"
    )
    
    try:
        result = client.ask(
            prompt=prompt,
            system="你是任务澄清专家。生成具体、有针对性的追问。只输出JSON。",
            force_model="thinking",
            temperature=0.4,
            max_tokens=300,
        )
        content = result.get("content", "")
        
        # 解析JSON - 取最后一个匹配（防鹦鹉学舌）
        content = content.strip()
        json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        if not json_matches:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            json_matches = [json_match.group()] if json_match else []
        if not json_matches:
            return None
        
        # 从最后一个匹配开始尝试
        for json_str in reversed(json_matches):
            try:
                parsed = json.loads(json_str)
                q1 = parsed.get("q1", "")
                q2 = parsed.get("q2", "")
                q3 = parsed.get("q3", "")
                
                if not (q1 and q2 and q3):
                    continue
                
                return (
                    f"**Q1. 成功标准是什么？**\n   {q1}\n\n"
                    f"**Q2. 边界在哪？**\n   {q2}\n\n"
                    f"**Q3. 风险预案？**\n   {q3}"
                )
            except (json.JSONDecodeError, ValueError, TypeError):
                continue
        
        
        # 降级：尝试逐字段提取
        for json_str in reversed(json_matches):
            q1_match = re.search(r'"q1"\s*:\s*"([^"]+)"', json_str)
            q2_match = re.search(r'"q2"\s*:\s*"([^"]+)"', json_str)
            q3_match = re.search(r'"q3"\s*:\s*"([^"]+)"', json_str)
            if q1_match and q2_match and q3_match:
                return (
                    f"**Q1. 成功标准是什么？**\n   {q1_match.group(1)}\n\n"
                    f"**Q2. 边界在哪？**\n   {q2_match.group(1)}\n\n"
                    f"**Q3. 风险预案？**\n   {q3_match.group(1)}"
                )
        
        return None
        
    except (json.JSONDecodeError, Exception):
        return None


# ============================================================
# MVP草稿生成
# ============================================================

def generate_mvp_draft(task_text: str) -> str:
    """
    生成"60分版本"骨架，让用户确认后再深度执行。
    MVP原则：先有能看的，再追求完美。
    """
    # 提取任务关键词
    keywords = re.findall(r'[\u4e00-\u9fa5a-zA-Z]{2,}', task_text)
    topic = "".join(keywords[:5]) if keywords else "未命名任务"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    draft_name = f"MVP_{topic[:8]}_{timestamp}.md"

    draft_content = f"""# MVP草稿：{task_text[:50]}

> 由 intent_clarifier.py 自动生成 | {datetime.now().strftime("%Y-%m-%d %H:%M")}

## 任务
{task_text}

## 预期成功标准
【待填写：什么是"完成"？】

## 范围
- [OK] **包含**：待填写
- ❌ **排除**：待填写

## 风险预案
【待填写：哪里最容易卡壳？】

## 骨架（60分版本）
【这里放一个"能看"的初稿框架，不需要完美】
- 第一步：...
- 第二步：...
- 第三步：...

---
> 请告诉我：这份草稿方向对吗？我再继续深化。
"""

    # 保存到历史目录
    draft_path = HISTORY_DIR / draft_name
    draft_path.write_text(draft_content, encoding="utf-8")

    return draft_content, str(draft_path)


# ============================================================
# 主接口：clarify_task
# ============================================================

def clarify_task(task_text: str, use_ai: bool = True) -> dict:
    """
    主接口：接收任务文本，返回决策和内容。
    
    use_ai: 是否启用AI语义增强（降级时传False）
    
    返回结构：
    {
        "action": "execute" | "clarify" | "mvp_confirm",
        "fuzziness": {...},
        "message": str,        # 显示给用户的文本
        "draft_path": str,     # MVP草稿路径（如有）
        "next_step": str       # 下一步指令
    }
    """
    fuzz = assess_fuzziness(task_text, use_ai=use_ai)

    # 极度模糊 → 输出三问 + MVP草稿
    if fuzz["score"] >= FUZZINESS_THRESHOLD:
        draft_content, draft_path = generate_mvp_draft(task_text)
        q3 = generate_3q(task_text, use_ai=use_ai)
        return {
            "action": "clarify",
            "fuzziness": fuzz,
            "message": (
                f"[!] 任务模糊度 **{fuzz['score']:.0%}**（{fuzz['level']}）\n"
                f"触发意图澄清流程。\n\n"
                f"**你的任务**：`{task_text[:80]}{'…' if len(task_text)>80 else ''}`\n\n"
                f"**疑点**：\n" + "\n".join(f"  {c}" for c in fuzz["clues"]) + "\n\n"
                f"{q3}\n\n"
                f"---\n\n"
                f"{draft_content}\n\n"
                f"MVP草稿已保存至：`{draft_path}`"
            ),
            "draft_path": draft_path,
            "next_step": "请回复【Q1/Q2/Q3的答案】，或告诉我草稿方向对不对。我确认后继续执行。"
        }

    # 微模糊 → 输出三问（但不暂停执行），用户可选择继续
    elif fuzz["score"] >= 0.3:
        q3 = generate_3q(task_text, use_ai=use_ai)
        return {
            "action": "clarify",
            "fuzziness": fuzz,
            "message": (
                f"[~] 任务微模糊 **{fuzz['score']:.0%}**（{fuzz['level']}）\n"
                f"**疑点**：\n" + "\n".join(f"  {c}" for c in fuzz["clues"]) + "\n\n"
                f"{q3}\n\n"
                f"**你可以选择**：\n"
                f"  A. 回答这3个问题 → 我重新评估\n"
                f"  B. 说\"继续执行\" → 我直接开干（可能走弯路）"
            ),
            "draft_path": None,
            "next_step": "A（回答3问）或 B（说\"继续执行\"）"
        }

    # 清晰 → 直接执行（实干优先）
    else:
        return {
            "action": "execute",
            "fuzziness": fuzz,
            "message": (
                f"[OK] 任务清晰度 **{1 - fuzz['score']:.0%}**（{fuzz['level']}）\n"
                f"直接执行。\n"
                f"**疑点**：\n" + "\n".join(f"  {c}" for c in fuzz["clues"]) + "\n\n"
                f"→ 开始干活。"
            ),
            "draft_path": None,
            "next_step": "执行中…"
        }


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    print("=" * 55)
    print("TU-8 L2 Intent Clarifier v2.0 - Test")
    print("=" * 55)

    # Test 0: AI可用性
    print("\n--- Test 0: AI Availability ---")
    client = _get_ollama_client()
    print(f"  Ollama available: {client is not None}")

    test_cases = [
        # 极度模糊
        "帮我搞一下",
        "看看那个东西",
        "somehow maybe do something",
        # 微模糊
        "帮我分析一下数据",
        "写一个脚本来处理文件",
        # 清晰
        "将 D:\\notes\\2026-05-16.md 的内容写入 memory/2026-05-16.md",
        "运行 streak_calculator.py 测试连击系统",
    ]

    # 规则vs AI 对比测试
    print("\n--- Test 1: Rule vs AI Comparison ---")
    for i, task in enumerate(test_cases, 1):
        rule_result = clarify_task(task, use_ai=False)
        ai_result = clarify_task(task, use_ai=True)
        r_score = rule_result['fuzziness']['score']
        a_score = ai_result['fuzziness']['score']
        delta = "↑" if a_score > r_score + 0.01 else "↓" if a_score < r_score - 0.01 else "="
        ai_tag = f"[AI:{ai_result['fuzziness'].get('ai_enhanced', False)}]"
        print(f"  {i}. [{delta}] {task[:25]:25s}  规则:{r_score:.0%} → AI:{a_score:.0%} {ai_tag}")

    # AI专属追问测试
    print("\n--- Test 2: AI vs Template Questions ---")
    vague_tasks = ["帮我搞一下", "分析一下那个问题"]
    for task in vague_tasks:
        print(f"\n  任务：{task}")
        template_q = generate_3q(task, use_ai=False)
        ai_q = generate_3q(task, use_ai=True)
        print(f"  [模板] {template_q[:80]}...")
        print(f"  [AI]   {ai_q[:80] if ai_q else 'N/A'}...")

    print("\n[Intent Clarifier v2.0 ready]")