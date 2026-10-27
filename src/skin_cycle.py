"""
skin_cycle.py — TU-8 脱皮+穿皮原子模块
=========================================
将 tu8_dispatch.py 中的 DawnRitual/DuskRitual 提取为独立原子操作，
供 consciousness_cycle 调用。

概念：
  脱皮（DuskRitual）= 打破旧状态：提取新钢印/因果链，写回本地
  穿皮（DawnRitual）= 建立新状态：加载本地结构 → 映射为云端神经元的灵魂

用法：
  from skin_cycle import SkinCycle
  skin = SkinCycle(workspace_dir)
  soul = skin.enter(user_input)       # 穿皮：进入会话
  result = skin.exit(response, soul)  # 脱皮：退出会话，写回本地
"""

import json
import time
import logging
from pathlib import Path
from typing import Optional

# ── 路径常量 ──────────────────────────────────────────────────
WS = Path("C:/Users/qq366410837/.qclaw/workspace")
AGENT = WS / "_agent_memory"

# ── 日志 ──────────────────────────────────────────────────────
logger = logging.getLogger("tu8.skin_cycle")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s %(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# ── 状态文件 ──────────────────────────────────────────────────
SKIN_CYCLE_STATE = AGENT / "skin_cycle_state.json"

def _read_state() -> dict:
    try:
        return json.loads(SKIN_CYCLE_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _write_state(state: dict):
    try:
        SKIN_CYCLE_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"写入 skin_cycle_state 失败: {e}")


# ── 核心类 ────────────────────────────────────────────────────
class SkinCycle:
    """
    脱皮+穿皮原子操作器。

    设计原则：
      - 穿皮：每次会话开始时调用，加载灵魂结构
      - 脱皮：每次会话结束时调用，提取并写回结构变更
      - 原子性：每个方法独立可调用，不相互依赖中间状态
      - 可重入：同一实例可处理多次穿皮-脱皮循环
    """

    def __init__(self, workspace_dir: str | None = None):
        ws = Path(workspace_dir) if workspace_dir else WS
        self.ws = ws
        self._soul_ref: Optional[object] = None
        self._enter_count: int = 0
        self._exit_count: int = 0
        self._last_enter_ts: Optional[str] = None
        self._last_exit_ts: Optional[str] = None

    # ── 穿皮（DawnRitual 封装）────────────────────────────────
    def enter(self, user_input: str = "") -> dict:
        """
        执行穿皮仪式：加载本地灵魂结构，映射为云端神经元的灵魂。

        Returns:
            soul_structure: 灵魂结构字典
              soul_hash       = seal_chain_hash（钢印链哈希）
              anchors         = active_memories（活跃锚点）
              seals           = recent_seals（近期钢印）
              causal_chains   = 因果链列表
              working_context_chars = 工作上下文长度
        """
        from tu8_dispatch import DawnRitual
        self._enter_count += 1
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        logger.info(f"[穿皮仪式 #{self._enter_count}] 开始加载灵魂结构...")
        try:
            ritual = DawnRitual(str(self.ws))
            soul_obj = ritual.execute(user_input)

            # SoulStructure 属性：seal_chain_hash / recent_seals / causal_chains / active_memories / working_context
            soul_structure = {
                "soul_hash":         getattr(soul_obj, "seal_chain_hash", ""),
                "anchors":           getattr(soul_obj, "active_memories", []),
                "seals":             getattr(soul_obj, "recent_seals", []),
                "causal_chains":     getattr(soul_obj, "causal_chains", []),
                "working_context_chars": len(getattr(soul_obj, "working_context", "") or ""),
                "enter_count":       self._enter_count,
                "ts":                ts,
            }
            self._soul_ref = soul_obj
            self._last_enter_ts = ts

            state = _read_state()
            state["last_enter"] = {
                "count": self._enter_count,
                "ts": ts,
                "soul_hash": soul_structure["soul_hash"],
            }
            state["total_enter"] = self._enter_count
            _write_state(state)

            logger.info(f"[穿皮仪式] 完成 soul_hash={soul_structure['soul_hash']}")
            return soul_structure

        except FileNotFoundError as e:
            logger.warning(f"[穿皮仪式] 文件未找到（首次启动？）: {e}")
            return {
                "soul_hash": "", "anchors": [], "seals": [], "causal_chains": [],
                "working_context_chars": 0, "enter_count": self._enter_count, "ts": ts,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"[穿皮仪式] 失败: {e}")
            return {
                "soul_hash": "", "anchors": [], "seals": [], "causal_chains": [],
                "working_context_chars": 0, "enter_count": self._enter_count, "ts": ts,
                "error": str(e)
            }

    # ── 脱皮（DuskRitual 封装）────────────────────────────────
    def exit(self, response_content: str, soul_structure: Optional[dict] = None) -> dict:
        """
        执行脱皮仪式：提取新的钢印/因果链，写回本地存储。

        Returns:
            result: 脱皮结果
              write_count / seal_count / chain_count / retry_count / payloads
        """
        from tu8_dispatch import DuskRitual

        # Mock soul object matching SoulStructure attribute names
        class _MockSoul:
            def __init__(self, d):
                self.seal_chain_hash  = d.get("soul_hash", "")
                self.active_memories   = d.get("anchors", [])
                self.recent_seals     = d.get("seals", [])
                self.causal_chains   = d.get("causal_chains", [])
                self.current_seal_id = d.get("current_seal_id") or None

        self._exit_count += 1
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        logger.info(f"[脱皮仪式 #{self._exit_count}] 开始提取结构...")
        try:
            mock_soul = _MockSoul(soul_structure or {})
            ritual = DuskRitual(str(self.ws))
            payloads = ritual.execute(response_content, mock_soul)

            # 统计：DuskRitual.execute() 返回结构
            #   - 空列表 [] = 验证失败的 WriteBackPayload（无效）
            #   - dict (type=RETRY) = 重试请求
            #   - dict (type=seal/chain) = 有效待写回
            seal_count  = sum(
                1 for p in payloads
                if isinstance(p, dict) and p.get("type") == "seal"
            )
            chain_count = sum(
                1 for p in payloads
                if isinstance(p, dict) and p.get("type") == "causal_chain"
            )
            retry_count = sum(
                1 for p in payloads
                if isinstance(p, dict) and p.get("type") == "RETRY"
            )
            # 有效写回：非空非重试的 dict
            write_count = sum(
                1 for p in payloads
                if isinstance(p, dict) and p.get("type") not in (None, "RETRY") and len(p) > 0
            )

            self._last_exit_ts = ts

            state = _read_state()
            state["last_exit"] = {
                "count": self._exit_count, "ts": ts,
                "write_count": write_count,
                "seal_count": seal_count,
                "chain_count": chain_count,
            }
            state["total_exit"] = self._exit_count
            _write_state(state)

            logger.info(f"[脱皮仪式] 完成 write={write_count} seals={seal_count} chains={chain_count} retry={retry_count}")
            return {
                "write_count": write_count,
                "seal_count": seal_count,
                "chain_count": chain_count,
                "retry_count": retry_count,
                "payloads": payloads,
                "exit_count": self._exit_count,
                "ts": ts,
            }

        except FileNotFoundError as e:
            logger.warning(f"[脱皮仪式] 文件未找到: {e}")
            return {
                "write_count": 0, "seal_count": 0, "chain_count": 0,
                "retry_count": 0, "payloads": [],
                "exit_count": self._exit_count, "ts": ts,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"[脱皮仪式] 失败: {e}")
            return {
                "write_count": 0, "seal_count": 0, "chain_count": 0,
                "retry_count": 0, "payloads": [],
                "exit_count": self._exit_count, "ts": ts,
                "error": str(e)
            }

    # ── 状态查询 ────────────────────────────────────────────────
    def status(self) -> dict:
        state = _read_state()
        return {
            "total_enter": state.get("total_enter", 0),
            "total_exit": state.get("total_exit", 0),
            "last_enter_ts": state.get("last_enter", {}).get("ts"),
            "last_exit_ts": state.get("last_exit", {}).get("ts"),
            "last_soul_hash": state.get("last_enter", {}).get("soul_hash", ""),
            "last_write_count": state.get("last_exit", {}).get("write_count", 0),
        }


# ── 便捷函数 ──────────────────────────────────────────────────
def enter_skin(user_input: str = "") -> dict:
    return SkinCycle().enter(user_input)

def exit_skin(response: str, soul_structure: Optional[dict] = None) -> dict:
    return SkinCycle().exit(response, soul_structure)


# ── CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TU-8 脱皮+穿皮原子操作")
    parser.add_argument("--enter", metavar="TEXT", help="执行穿皮仪式（加载灵魂结构）")
    parser.add_argument("--exit", metavar="TEXT", help="执行脱皮仪式（写回结构）")
    parser.add_argument("--status", action="store_true", help="查看当前皮肤循环状态")
    args = parser.parse_args()

    skin = SkinCycle()
    if args.enter is not None:
        result = skin.enter(args.enter)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.exit is not None:
        result = skin.exit(args.exit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.status:
        print(json.dumps(skin.status(), ensure_ascii=False, indent=2))
    else:
        parser.print_help()
