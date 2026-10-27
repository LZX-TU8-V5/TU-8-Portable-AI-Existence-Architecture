# -*- coding: utf-8 -*-
"""
src/algebraic_protocol.py -- Algebraic Interface Protocol
=========================================================

Protocol goal: enforce strict separation between
  - Definition Layer (pure algebraic, zero transcendental)
  - Evaluation Layer (may use transcendental for speed)

Pi-Erasability Test:
  Replace pi with symbol P. Can you cancel it out algebraically?

  YES  -> safe computation accelerator (syntax sugar)  [OK]
  NO   -> state pollution (must refactor)             [FAIL]
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SRC_DIR = Path(__file__).parent

# Definition layer blacklist
TRANSCENDENTAL_BLACKLIST = [
    "math.pi", "numpy.pi", "math.e",
    "math.cos", "math.sin", "math.tan",
    "math.acos", "math.asin", "math.atan", "math.atan2",
    "math.radians", "math.degrees",
    "math.exp", "math.log", "math.log10", "math.log1p", "math.pow",
    "numpy.exp", "numpy.log", "numpy.cos", "numpy.sin",
]

# Init functions: allowed to use transcendental (called once at startup, not hot)
INIT_FUNCTIONS = {
    "_build_trig_table",           # tu8_health_orb_ring
    "_build_trig_table_360",       # tu8_health_orb_ps
    "_build_sphere_directions",     # topology_connector
    "build_hue_ring_ppm",          # tu8_health_orb_ring: PPM generation at startup
}


class TranscendentalVisitor(ast.NodeVisitor):
    """
    Walk AST, collect all transcendental function calls.

    Context tracking:
      - _hot_depth: how many hot-path-function scopes we're inside
        (nested helper functions INCREASE this depth)
      - Violation is 'hot path' if _hot_depth > 0
        (i.e., the call happens inside the hot path or a nested helper)

    Why depth-based: when refresh() calls _ball_xy_by_name(), we enter
    _ball_xy_by_name's FunctionDef before processing its body. Depth
    correctly tracks "we are still inside refresh's scope" even after
    entering _ball_xy_by_name's definition node.
    """

    def __init__(self, hot_path: Optional[str] = None):
        self.hot_path_name = hot_path
        self._hot_depth: int = 0  # nested hot-path scope depth
        self._func_stack: List[str] = []  # track current function context
        self.violations: List[Dict] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old_depth = self._hot_depth
        old_stack_len = len(self._func_stack)

        # Push function onto stack
        self._func_stack.append(node.name)

        # Increase hot depth if entering a hot-path function
        # (nested helpers increase the depth, so we stay "in hot path")
        if node.name == self.hot_path_name:
            self._hot_depth += 1

        # Visit body
        self.generic_visit(node)

        # Pop and restore depth
        self._func_stack.pop()
        self._hot_depth = old_depth

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                lib = node.func.value.id
                name = node.func.attr
                full = f"{lib}.{name}"

                if full in TRANSCENDENTAL_BLACKLIST:
                    in_hot = self._hot_depth > 0
                    current_func = (self._func_stack[-1] if self._func_stack
                                    else "<module>")
                    self.violations.append({
                        "function": current_func,
                        "call": full,
                        "line": node.lineno,
                        "hot_path": in_hot,
                    })

        self.generic_visit(node)


def check_hot_path(module_name: str, hot_path: str) -> Tuple[bool, List[Dict]]:
    """Check if hot path is free of transcendental calls."""
    src_path = SRC_DIR / f"{module_name}.py"
    if not src_path.exists():
        return False, [{"error": f"Module {module_name}.py not found"}]

    source = src_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=f"{module_name}.py")

    visitor = TranscendentalVisitor(hot_path=hot_path)
    visitor.visit(tree)

    return len(visitor.violations) == 0, visitor.violations


def verify_module(module_name: str) -> Dict:
    """
    Full protocol verification for a module.

    Returns:
        algebraic:        definition layer has zero transcendental
        hot_paths:        per-hot-path check results
        has_trig_table:  precomputed table present
        total_trans:      total transcendental calls (all)
        summary:          human-readable summary
    """
    src_path = SRC_DIR / f"{module_name}.py"
    if not src_path.exists():
        return {"error": f"Module {module_name}.py not found"}

    source = src_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=f"{module_name}.py")

    global_visitor = TranscendentalVisitor(hot_path=None)
    global_visitor.visit(tree)

    known_hot = {
        "tu8_health_orb_ring": "refresh",
        "tu8_health_orb_ps": "update_state",
        "topology_connector": "add_node",
    }
    detected_hot = known_hot.get(module_name)

    hot_paths = {}
    if detected_hot:
        clean, all_viols = check_hot_path(module_name, detected_hot)
        # Only count hot_path=True violations as failures
        hot_only = [v for v in all_viols if v["hot_path"]]
        hot_paths[detected_hot] = {"clean": len(hot_only) == 0, "violations": hot_only}
    has_table = any(x in source for x in [
        "_BALL_TRIG", "_TRIG_360", "_SPHERE_DIRECTIONS",
        "_build_trig_table", "_build_sphere_directions",
    ])

    hot_funcs = {k for k in hot_paths}
    # Init functions: called once at startup, allowed to use transcendental
    definition_violations = [
        v for v in global_visitor.violations
        if v["function"] not in hot_funcs
        and v["function"] not in INIT_FUNCTIONS
    ]

    hot_clean = hot_paths and all(info["clean"] for info in hot_paths.values())
    def_clean = len(definition_violations) == 0

    if hot_clean and def_clean:
        summary = "[OK] algebraic: hot path zero trans, init whitelisted, definition layer clean"
    elif hot_clean:
        summary = f"[WARN] hot path clean, definition layer has {len(definition_violations)} trans call(s)"
    elif hot_paths:
        hot_only = sum(1 for info in hot_paths.values() for v in info["violations"] if v["hot_path"])
        summary = f"[FAIL] hot path has {hot_only} hot-path violation(s)"
    else:
        summary = "[INFO] no hot path detected"

    return {
        "algebraic": def_clean and hot_clean,
        "hot_paths": hot_paths,
        "has_trig_table": has_table,
        "total_transcendental": len(global_visitor.violations),
        "definition_violations": definition_violations,
        "summary": summary,
    }


def print_algebraic_summary(module_name: str) -> None:
    """Print human-readable summary."""
    result = verify_module(module_name)
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"Algebraic Protocol: {module_name}.py")
    print(sep)
    print(f"Summary : {result.get('summary', result.get('error', 'unknown'))}")
    print(f"TrigTable: {'[YES]' if result.get('has_trig_table') else '[NO]'}")
    print(f"Algebraic: {'[OK]' if result.get('algebraic') else '[FAIL]'}")

    hp = result.get("hot_paths", {})
    if hp:
        print(f"\nHot path checks:")
        for name, info in hp.items():
            status = "[OK]" if info["clean"] else f"[FAIL] {len(info['violations'])} violation(s)"
            print(f"  {name}(): {status}")
            for v in info["violations"]:
                print(f"    L{v['line']}: {v['call']}")

    def_v = result.get("definition_violations", [])
    if def_v:
        print(f"\nDefinition layer pollution ({len(def_v)}):")
        for v in def_v[:5]:
            print(f"  {v['function']}() L{v['line']}: {v['call']}")
    print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for module in sys.argv[1:]:
            print_algebraic_summary(module)
    else:
        for module in ["tu8_health_orb_ring", "tu8_health_orb_ps", "topology_connector"]:
            print_algebraic_summary(module)
