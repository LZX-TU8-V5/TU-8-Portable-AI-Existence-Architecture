"""
codebook.py — 密文库（符号↔实体 字典注册表）[H 级批次3, 2026-08-29 落地]

设计稿：docs/design/topic_matrix_impl_design_2026-08-28.md §6
职责：
  - 符号级无损压缩字典：sym_* -> ent_*（实体注册表）
  - 跨引用枢纽：记忆卡用 sym 短码代替长实体名，降 token 膨胀
  - 与 grounding（有向溯源）/ 知识组织（定义内容）三层各管一摊（v1.3 §14）
  - 挂载 secure_vault/index.json 的 codebook 键（铁律五：不新建散落文件）

范围（§12 决策）：仅注册表。不含 entity_resolver 知识组织层（留后续）。

接口契约（设计稿 §6）：
  register(label, event_id) -> sym_*
  resolve(sym) -> {"entity_id","label","created_event",...}
  save() -> 写回 index.json["codebook"]
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Optional

WORKSPACE = Path(os.environ.get("QCLAW_WORKSPACE",
                                str(Path.home() / ".qclaw" / "workspace")))
INDEX_PATH = WORKSPACE / "secure_vault" / "index.json"


def _slug(label: str) -> str:
    """label -> 短码（中文保留，去空格标点）。"""
    s = re.sub(r"[\s\W]+", "", label)
    return s[:12] if s else "x"


def _checksum(label: str) -> str:
    """label -> 4 位校验位（防同名 label 碰撞漂移）。"""
    return hashlib.md5(label.encode("utf-8")).hexdigest()[:4]


def _load_index() -> dict:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {}


def _load_codebook() -> dict:
    idx = _load_index()
    return idx.get("codebook", {})


def _save_codebook(data: dict) -> None:
    idx = _load_index()
    idx["codebook"] = data
    idx["updated"] = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


class Codebook:
    def __init__(self):
        self.data: dict = _load_codebook()

    def register(self, label: str, event_id: str, aliases: Optional[list] = None) -> str:
        """注册实体，返回 sym_* 短码。同名 label 复用已有 sym（幂等）。
        aliases: 同义异构表述（我妈/母亲/老太太），归并到同一 sym（§0.1 记忆融合，防分裂）。"""
        # 幂等：已注册同 label 直接返回
        for sym, rec in self.data.items():
            if rec.get("label") == label:
                return sym
        sym = f"sym_{_slug(label)}_{_checksum(label)}"
        rec = {
            "entity_id": f"ent_{_checksum(label)}",
            "label": label,
            "created_event": event_id,
            "aliases": list(aliases) if aliases else [],
            # axis_weights 运行时由 distill 反推（§1.8 非手填），初始空
            "axis_weights": {},
        }
        self.data[sym] = rec
        self.save()
        return sym

    def merge_alias(self, sym: str, alias: str) -> bool:
        """P0 #3：把同义表述并入已有 sym（显式纠偏/用户归并）。
        返回 True 若该 alias 之前是独立 sym（被吸收）。"""
        if sym not in self.data:
            return False
        # 若 alias 本身是独立 sym，吸收其记录后删除
        absorbed = alias in self.data
        if absorbed:
            old = self.data.pop(alias)
            # 旧 sym 的 axis_weights 并入（平均），aliases 继承
            self._merge_weights(sym, old.get("axis_weights", {}))
            for a in old.get("aliases", []):
                if a not in self.data[sym]["aliases"]:
                    self.data[sym]["aliases"].append(a)
        if alias not in self.data[sym]["aliases"]:
            self.data[sym]["aliases"].append(alias)
        self.save()
        return absorbed

    def _merge_weights(self, sym: str, incoming: dict, weight: float = 0.5) -> None:
        """axis_weights 平滑合并（运行时反推，非手填）。"""
        cur = self.data[sym].get("axis_weights", {})
        for k, v in incoming.items():
            cur[k] = cur.get(k, 0.0) * (1 - weight) + v * weight
        self.data[sym]["axis_weights"] = cur

    def update_axis_weights(self, sym: str, coord: dict, weight: float = 0.3) -> None:
        """§1.8：distill 写入段 coord 后反推 sym 轴分布（涌现非手写）。
        coord: {sem,ctx,act} -> 对应轴 +1.0，与历史平均。"""
        if sym not in self.data:
            return
        inc = {}
        for axis in (coord.get("sem"), coord.get("ctx"), coord.get("act")):
            if axis:
                inc[axis] = 1.0
        self._merge_weights(sym, inc, weight)
        self.save()

    def resolve(self, sym: str) -> Optional[dict]:
        """sym_* -> 实体记录（entity_id/label/created_event/aliases/axis_weights）。"""
        return self.data.get(sym)

    def resolve_by_alias(self, text: str) -> Optional[str]:
        """P0 #3：文本命中 alias/label -> sym（模糊归并检索）。"""
        for sym, rec in self.data.items():
            if text == rec.get("label") or text in rec.get("aliases", []):
                return sym
        return None

    def resolve_label(self, sym: str) -> Optional[str]:
        """sym_* -> 明文 label（还原用）。"""
        rec = self.data.get(sym)
        return rec.get("label") if rec else None

    def all_syms(self) -> list[str]:
        return list(self.data.keys())

    def save(self) -> None:
        _save_codebook(self.data)


if __name__ == "__main__":
    cb = Codebook()
    # 高频繁体（苹果/TU-8/七七）压短码
    s1 = cb.register("苹果", "evt_apple_001")
    s2 = cb.register("TU-8", "evt_tu8_001")
    s3 = cb.register("七七", "evt_qiqi_001")
    print("register 苹果:", s1, "resolve:", cb.resolve_label(s1))
    print("register TU-8:", s2, "resolve:", cb.resolve_label(s2))
    print("register 七七:", s3, "resolve:", cb.resolve_label(s3))
    # 幂等验证
    s1b = cb.register("苹果", "evt_apple_002")
    print("idempotent 苹果:", s1b == s1)
    # codebook 键已写入 index.json
    idx = _load_index()
    print("index.json has codebook:", "codebook" in idx, "entries:", len(idx["codebook"]))
    print("CODEBOOK OK")
