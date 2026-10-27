"""TU-8 审计规则引擎 — 用确定性代码约束概率性AI生成

不是"请反思你的代码"，而是 assert len(func_lines) <= 50。
哲学不能阻止屎山，机器能。

作者: TU-8 / 金木蟾
协议: CC BY-SA 4.0
"""
import ast
import re
import textwrap
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Callable


@dataclass
class Violation:
    """单条违规"""
    rule_id: str
    severity: str          # CRITICAL / WARNING / INFO
    message: str
    file: str = ""
    line: int = 0
    function: str = ""
    suggestion: str = ""


@dataclass
class AuditRule:
    """审计规则定义"""
    rule_id: str
    name: str
    severity: str
    check: Callable        # (source_code, filepath) -> List[Violation]


class AuditEngine:
    """确定性审计引擎 — 大厂规范的机器可执行形式"""

    def __init__(self):
        self.rules: List[AuditRule] = []
        self._register_builtin_rules()

    # ----- 内置规则注册 -----

    def _register_builtin_rules(self):
        """注册核心审计规则 — 对应大厂规范中最有约束力的条目"""

        # R001: 函数体不超过50行（阿里Java手册 §8.1 / Google Style §5.2）
        self.rules.append(AuditRule(
            rule_id="R001",
            name="函数体行数上限",
            severity="WARNING",
            check=self._check_function_length
        ))

        # R002: 禁止裸 except（阿里Java手册 §8.4 / PEP8）
        self.rules.append(AuditRule(
            rule_id="R002",
            name="禁止裸except",
            severity="CRITICAL",
            check=self._check_bare_except
        ))

        # R003: 禁止硬编码密钥/Token
        self.rules.append(AuditRule(
            rule_id="R003",
            name="禁止硬编码密钥",
            severity="CRITICAL",
            check=self._check_hardcoded_secrets
        ))

        # R004: 类方法数不超过20（单一职责）
        self.rules.append(AuditRule(
            rule_id="R004",
            name="类方法数上限",
            severity="WARNING",
            check=self._check_class_method_count
        ))

        # R005: 禁止 TODO/FIXME 遗留（代码可交付性检查）
        self.rules.append(AuditRule(
            rule_id="R005",
            name="禁止TODO/FIXME遗留",
            severity="INFO",
            check=self._check_todo_fixme
        ))

        # R006: 禁止 import *（命名空间污染）
        self.rules.append(AuditRule(
            rule_id="R006",
            name="禁止import星号",
            severity="WARNING",
            check=self._check_wildcard_import
        ))

        # R007: 文件行数不超过500（可读性边界）
        self.rules.append(AuditRule(
            rule_id="R007",
            name="文件行数上限",
            severity="WARNING",
            check=self._check_file_length
        ))

        # R008: 禁止深层嵌套（>4层缩进 = 逻辑复杂度过高）
        self.rules.append(AuditRule(
            rule_id="R008",
            name="禁止深层嵌套",
            severity="WARNING",
            check=self._check_deep_nesting
        ))

        # R009: 静默吞没检测 — except ... : pass/continue 无日志
        self.rules.append(AuditRule(
            rule_id="R009",
            name="静默吞没检测",
            severity="WARNING",
            check=self._check_silent_swallow
        ))

    # ----- 规则实现 -----

    def _check_function_length(self, source: str, filepath: str) -> List[Violation]:
        violations = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return violations

        source_lines = source.splitlines()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = getattr(node, 'end_lineno', start)
                length = end - start + 1
                if length > 50:
                    violations.append(Violation(
                        rule_id="R001", severity="WARNING",
                        message=f"函数 {node.name} 有 {length} 行（上限50）",
                        file=filepath, line=start, function=node.name,
                        suggestion="拆分为更小的函数，每个只做一件事"
                    ))
        return violations

    def _check_bare_except(self, source: str, filepath: str) -> List[Violation]:
        violations = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    violations.append(Violation(
                        rule_id="R002", severity="CRITICAL",
                        message="裸 except: 会吞掉所有异常包括 KeyboardInterrupt",
                        file=filepath, line=node.lineno,
                        suggestion="改为 except Exception: 或更具体的异常类型"
                    ))
        return violations

    def _check_hardcoded_secrets(self, source: str, filepath: str) -> List[Violation]:
        violations = []
        patterns = [
            (r'(?i)(api_key|apikey|secret|token|password|pwd)\s*=\s*["\'][^"\']{8,}["\']',
             "疑似硬编码密钥/Token"),
            (r'(?i)(sk-[a-zA-Z0-9]{20,})',
             "疑似 OpenAI API Key"),
            (r'(?i)(AKIA[0-9A-Z]{16})',
             "疑似 AWS Access Key"),
        ]
        for i, line in enumerate(source.splitlines(), 1):
            for pattern, msg in patterns:
                if re.search(pattern, line):
                    violations.append(Violation(
                        rule_id="R003", severity="CRITICAL",
                        message=msg, file=filepath, line=i,
                        suggestion="使用环境变量或配置文件，禁止硬编码"
                    ))
        return violations

    def _check_class_method_count(self, source: str, filepath: str) -> List[Violation]:
        violations = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if len(methods) > 20:
                    violations.append(Violation(
                        rule_id="R004", severity="WARNING",
                        message=f"类 {node.name} 有 {len(methods)} 个方法（上限20）",
                        file=filepath, line=node.lineno,
                        suggestion="违反单一职责，拆分为多个类"
                    ))
        return violations

    def _check_todo_fixme(self, source: str, filepath: str) -> List[Violation]:
        violations = []
        for i, line in enumerate(source.splitlines(), 1):
            if re.search(r'\b(TODO|FIXME|HACK|XXX)\b', line, re.IGNORECASE):
                violations.append(Violation(
                    rule_id="R005", severity="INFO",
                    message=f"遗留标记: {line.strip()[:60]}",
                    file=filepath, line=i,
                    suggestion="处理或转为正式 Issue 跟踪"
                ))
        return violations

    def _check_wildcard_import(self, source: str, filepath: str) -> List[Violation]:
        violations = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == '*':
                        violations.append(Violation(
                            rule_id="R006", severity="WARNING",
                            message=f"from {node.module} import * 污染命名空间",
                            file=filepath, line=node.lineno,
                            suggestion="显式导入需要的名称"
                        ))
        return violations

    def _check_file_length(self, source: str, filepath: str) -> List[Violation]:
        violations = []
        line_count = len(source.splitlines())
        if line_count > 500:
            violations.append(Violation(
                rule_id="R007", severity="WARNING",
                message=f"文件有 {line_count} 行（上限500）",
                file=filepath,
                suggestion="拆分为多个模块，单一职责"
            ))
        return violations

    def _check_deep_nesting(self, source: str, filepath: str) -> List[Violation]:
        violations = []
        for i, line in enumerate(source.splitlines(), 1):
            # 计算前导空格/制表符对应的缩进层级
            stripped = line.lstrip()
            if not stripped or stripped.startswith('#'):
                continue
            indent = len(line) - len(stripped)
            # 假设4空格=1层或1制表符=1层
            if line[:indent].count('\t') > 0:
                level = line[:indent].count('\t')
            else:
                level = indent // 4
            if level > 4:
                violations.append(Violation(
                    rule_id="R008", severity="WARNING",
                    message=f"嵌套深度 {level} 层（上限4）",
                    file=filepath, line=i,
                    suggestion="提取内层逻辑为独立函数（卫语句/早返回）"
                ))
        return violations

    def _check_silent_swallow(self, source: str, filepath: str) -> List[Violation]:
        """R009: 检测 except 块中 pass/continue 后无日志的静默吞没"""
        violations = []
        lines = source.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            # Match except clause (with specific type, not bare — that's R002)
            # Note: except can be at indent 0 (top-level) or indented
            if re.match(r'^\s*except\s+', line) and not re.match(r'^\s*except\s*:', line):
                # Look ahead for pass/continue in the except body
                j = i + 1
                has_log = False
                has_pass_or_continue = False
                except_indent = len(lines[i]) - len(lines[i].lstrip())
                while j < len(lines):
                    body_line = lines[j]
                    body_stripped = body_line.strip()
                    body_indent = len(body_line) - len(body_line.lstrip()) if body_stripped else except_indent + 4
                    # If we've de-dented, we've left the except block
                    if body_stripped and body_indent <= except_indent:
                        break
                    # Check for logging call
                    if re.search(r'(logger|logging|log)\s*[.(]', body_stripped):
                        has_log = True
                    # Check for pass/continue
                    if body_stripped in ('pass', 'continue'):
                        has_pass_or_continue = True
                    j += 1
                if has_pass_or_continue and not has_log:
                    violations.append(Violation(
                        rule_id="R009", severity="WARNING",
                        message="except 块含 pass/continue 但无日志，异常被静默吞没",
                        file=filepath, line=i + 1,
                        suggestion="添加 logger.debug(..., exc_info=True) 或 logger.warning(...)"
                    ))
            i += 1
        return violations

    # ----- 执行入口 -----

    def audit_file(self, filepath: str) -> List[Violation]:
        """审计单个文件"""
        source = Path(filepath).read_text(encoding='utf-8', errors='replace')
        all_violations = []
        for rule in self.rules:
            try:
                violations = rule.check(source, filepath)
                all_violations.extend(violations)
            except Exception as e:
                all_violations.append(Violation(
                    rule_id=rule.rule_id, severity="INFO",
                    message=f"规则执行异常: {e}", file=filepath
                ))
        return all_violations

    def audit_directory(self, dirpath: str, *,
                        suffixes: tuple = (".py",),
                        exclude: tuple = ("__pycache__", ".git", "node_modules", "venv", "_corrupted_backup")
                        ) -> dict:
        """审计整个目录"""
        all_violations = []
        files_scanned = 0
        root = Path(dirpath)

        for f in root.rglob("*"):
            if f.suffix not in suffixes:
                continue
            if any(exc in str(f) for exc in exclude):
                continue
            files_scanned += 1
            violations = self.audit_file(str(f))
            all_violations.extend(violations)

        # 按严重度分组
        critical = [v for v in all_violations if v.severity == "CRITICAL"]
        warning = [v for v in all_violations if v.severity == "WARNING"]
        info = [v for v in all_violations if v.severity == "INFO"]

        return {
            "files_scanned": files_scanned,
            "total_violations": len(all_violations),
            "critical": len(critical),
            "warning": len(warning),
            "info": len(info),
            "violations": all_violations,
            "pass": len(critical) == 0  # 有CRITICAL就不通过
        }

    def format_report(self, result: dict) -> str:
        """格式化审计报告"""
        lines = [
            "=" * 60,
            "TU-8 审计报告",
            "=" * 60,
            f"扫描文件: {result['files_scanned']}",
            f"总违规数: {result['total_violations']}",
            f"  CRITICAL: {result['critical']}",
            f"  WARNING:  {result['warning']}",
            f"  INFO:     {result['info']}",
            f"审计结果: {'✅ PASS' if result['pass'] else '❌ FAIL (存在CRITICAL)'}",
            "=" * 60,
        ]

        # 按严重度排序输出
        severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
        sorted_v = sorted(result["violations"],
                         key=lambda v: (severity_order.get(v.severity, 9), v.file, v.line))

        current_file = ""
        for v in sorted_v:
            if v.file != current_file:
                current_file = v.file
                lines.append(f"\n--- {v.file} ---")
            icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(v.severity, "⚪")
            loc = f"L{v.line}" if v.line else ""
            func = f" {v.function}()" if v.function else ""
            lines.append(f"  {icon} [{v.rule_id}] {loc}{func}: {v.message}")
            if v.suggestion:
                lines.append(f"     → {v.suggestion}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    engine = AuditEngine()

    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = r"C:\Users\qq366410837\.qclaw\workspace\src"

    if Path(target).is_file():
        violations = engine.audit_file(target)
        result = {
            "files_scanned": 1,
            "total_violations": len(violations),
            "critical": sum(1 for v in violations if v.severity == "CRITICAL"),
            "warning": sum(1 for v in violations if v.severity == "WARNING"),
            "info": sum(1 for v in violations if v.severity == "INFO"),
            "violations": violations,
            "pass": all(v.severity != "CRITICAL" for v in violations)
        }
    else:
        result = engine.audit_directory(target)

    print(engine.format_report(result))
