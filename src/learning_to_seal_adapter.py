"""
learning_to_seal_adapter.py — T5→T2 中间件：学习产物→钢印铸造

功能：
  当学习链 Phase 5 应用成功后，
  自动铸造一条新的钢印记录到 seal_index.json，
  实现学习产物到决策历史的闭环。
  
  类比：学习发现了新规律 → 这规律本身成为"认知签名"的一部分
"""

import json
import os
import time
from pathlib import Path

WORKSPACE = Path(os.environ.get("TU8_WORKSPACE", os.environ.get("QCLAW_WORKSPACE",
    os.path.expanduser("~/.qclaw/workspace"))))

SEAL_INDEX = WORKSPACE / "memory" / "time_chain" / "seal_index.json"


def _read_seals() -> list:
    """读取现有钢印列表"""
    if not SEAL_INDEX.exists():
        return []
    try:
        seals = json.loads(SEAL_INDEX.read_text(encoding="utf-8"))
        if isinstance(seals, dict):
            seals = list(seals.values())
        return seals if isinstance(seals, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_seals(seals: list):
    """保存钢印列表"""
    SEAL_INDEX.parent.mkdir(parents=True, exist_ok=True)
    SEAL_INDEX.write_text(
        json.dumps(seals, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def cast_learning_seal(product: dict) -> dict:
    """
    从学习产物铸造一条新钢印。

    参数:
        product: learning_connect 阶段产出的标准产物字典
                 {id, type, content, action, confidence, track, ...}

    返回:
        {"sealed": True, "seal_id": "seal_...", "scene_tag": str}
        {"sealed": False, "reason": str}
    """
    # 只有足够置信的产物才值得铸印
    confidence = product.get("confidence", 0)
    if confidence < 0.6:
        return {"sealed": False, "reason": f"confidence {confidence} < 0.6"}

    content = product.get("content", "")
    if not content:
        return {"sealed": False, "reason": "empty content"}

    product_type = product.get("type", "MEMO")
    action = product.get("action", "")
    pid = product.get("id", "?")

    # 铸印
    seal_id = f"seal_{int(time.time())}_{pid[:8]}"
    scene_tag = f"learning:{product_type.lower()}"
    narrative_ref = content[:200] if isinstance(content, str) else str(content)[:200]

    seal_entry = {
        "seal_id": seal_id,
        "parent_seal": "",
        "scene_tag": scene_tag,
        "summary": narrative_ref,
        "timestamp": time.time(),
        "source": "learning_chain",
        "product_id": pid,
        "product_type": product_type,
        "product_confidence": round(confidence, 3),
        "product_action": action,
    }

    seals = _read_seals()
    seals.append(seal_entry)
    _save_seals(seals)

    print(f"[T5→T2] 铸印: {seal_id} ({scene_tag})")
    return {"sealed": True, "seal_id": seal_id, "scene_tag": scene_tag}


def on_apply(product: dict) -> dict:
    """
    Phase 5 apply 时的钩子，由 learning_apply.py 调用。
    只在置信度 >= 0.6 的产物上铸印。
    """
    return cast_learning_seal(product)


if __name__ == "__main__":
    # 测试
    test_products = [
        {"id": "lp_alert_001", "type": "ALERT", "content": "检测到情绪低落模式", 
         "confidence": 0.85, "action": "notify_creator", "track": "palace"},
        {"id": "lp_intu_001", "type": "INTUITION", "content": "用户偏好极简确认",
         "confidence": 0.72, "action": "inject_intuition", "track": "palace"},
        {"id": "lp_low_001", "type": "MEMO", "content": "不确定的猜测",
         "confidence": 0.45, "action": "append_memory", "track": "palace"},
    ]

    for p in test_products:
        r = cast_learning_seal(p)
        print(f"  {p['id']}: {json.dumps(r, ensure_ascii=False)}")

    # 验证最终钢印数量
    final = _read_seals()
    print(f"\nTotal seals: {len(final)}")
