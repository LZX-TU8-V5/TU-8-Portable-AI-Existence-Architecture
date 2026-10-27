"""
TU-8 记忆宫殿 2.0：存量 .md 文件扫描与脱敏脚本

用途：在 enable_protection=true 开启前，先对存量 .md 文件进行离线扫描与脱敏
      避免旧文件中的敏感信息在运行时被 STDP 强化后泄露

⚠️ 注意：此脚本为一次性离线任务，执行后不可逆

Author: TU-8 (金木蟾)
Date: 2026-05-29
"""

import re
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Tuple, Optional

# 添加脚本路径
sys.path.insert(0, str(Path(__file__).parent))
from memory_protection import PrivacySanitizer, ProtectionClassifier


# ============================================================
# 配置
# ============================================================

# 扫描目录（需要根据实际情况修改）
SCAN_DIRECTORIES = [
    "D:/qq366410837/.qclaw/workspace/knowledge",
    "D:/qq366410837/.qclaw/workspace/memory",
    "D:/qq366410837/.qclaw/workspace/journal",
]

# 备份目录
BACKUP_DIRECTORY = "D:/qq366410837/.qclaw/workspace/backups/md_scan"

# 文件扩展名
FILE_EXTENSIONS = [".md", ".txt", ".markdown"]

# 脱敏规则
SANITIZER = PrivacySanitizer(enable_time_obfuscation=False)  # 存量文件保留时间戳


# ============================================================
# 敏感信息检测
# ============================================================

class SensitiveScanner:
    """敏感信息扫描器"""
    
    # 高风险模式（必须扫描）
    HIGH_RISK_PATTERNS = [
        (r"\b\d{17}[\dXx]\b", "身份证号"),
        (r"\b1[3-9]\d{9}\b", "手机号"),
        (r"(?:密码|口令|token|password)\s*[:：]?\s*\S+", "密码/凭证"),
    ]
    
    # 中风险模式（建议扫描）
    MEDIUM_RISK_PATTERNS = [
        (r"(?:确诊|患有|诊断为)\s*[\u4e00-\u9fa5]{2,10}", "健康信息"),
        (r"(?:工资|收入|存款|薪资)\s*(?:约|大概)?\s*\d+[\w]*", "财务信息"),
    ]
    
    @classmethod
    def scan_file(cls, file_path: str) -> List[Tuple[str, str, str, int]]:
        """
        扫描文件中的敏感信息
        
        Returns:
            List of (line_content, pattern, description, line_number)
        """
        findings = []
        
        # 尝试多种编码
        for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    for line_num, line in enumerate(f, 1):
                        # 高风险模式
                        for pattern, description in cls.HIGH_RISK_PATTERNS:
                            if re.search(pattern, line, re.IGNORECASE):
                                findings.append((line.strip(), pattern, f"[高风险] {description}", line_num))
                        
                        # 中风险模式
                        for pattern, description in cls.MEDIUM_RISK_PATTERNS:
                            if re.search(pattern, line, re.IGNORECASE):
                                findings.append((line.strip(), pattern, f"[中风险] {description}", line_num))
                break  # 成功读取，退出编码尝试
            except UnicodeDecodeError:
                continue
        
        return findings
    
    @classmethod
    def scan_directory(cls, directory: str, recursive: bool = True) -> dict:
        """
        扫描目录下所有文件
        
        Returns:
            Dict of {file_path: [(line_content, pattern, description, line_num), ...]}
        """
        results = {}
        directory_path = Path(directory)
        
        if not directory_path.exists():
            print(f"[WARN] 目录不存在: {directory}")
            return results
        
        # 获取所有 .md 文件
        if recursive:
            files = list(directory_path.rglob("*.md")) + list(directory_path.rglob("*.markdown"))
        else:
            files = list(directory_path.glob("*.md")) + list(directory_path.glob("*.markdown"))
        
        for file_path in files:
            findings = cls.scan_file(str(file_path))
            if findings:
                results[str(file_path)] = findings
        
        return results


# ============================================================
# 脱敏处理
# ============================================================

class MDProcessor:
    """Markdown 文件脱敏处理器"""
    
    def __init__(self, dry_run: bool = True):
        """
        Args:
            dry_run: True=仅模拟，False=实际执行脱敏
        """
        self.dry_run = dry_run
        self.sanitizer = PrivacySanitizer(enable_time_obfuscation=False)
        self.processed_count = 0
        self.total_findings = 0
    
    def process_file(self, file_path: str) -> bool:
        """
        处理单个文件
        
        Returns:
            True if modified, False otherwise
        """
        # 读取文件
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 脱敏处理
        sanitized = self.sanitizer.sanitize(content, protection_level=0)
        
        # 检查是否有变化
        if sanitized == content:
            return False
        
        # 备份原文件
        if not self.dry_run:
            backup_path = self._create_backup(file_path)
            print(f"  备份: {backup_path}")
        
        # 写入脱敏后的内容
        if not self.dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(sanitized)
        
        self.processed_count += 1
        return True
    
    def _create_backup(self, file_path: str) -> str:
        """创建备份文件"""
        backup_dir = Path(BACKUP_DIRECTORY)
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成备份文件名（添加时间戳）
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = Path(file_path).name
        backup_path = backup_dir / f"{filename}.backup_{timestamp}"
        
        # 复制文件
        import shutil
        shutil.copy2(file_path, backup_path)
        
        return str(backup_path)
    
    def process_directory(self, directory: str, recursive: bool = True) -> dict:
        """
        处理目录下所有文件
        
        Returns:
            Dict of {file_path: status}
        """
        results = {}
        directory_path = Path(directory)
        
        if not directory_path.exists():
            return results
        
        # 获取所有 .md 文件
        if recursive:
            files = list(directory_path.rglob("*.md")) + list(directory_path.rglob("*.markdown"))
        else:
            files = list(directory_path.glob("*.md")) + list(directory_path.glob("*.markdown"))
        
        for file_path in files:
            try:
                modified = self.process_file(str(file_path))
                results[str(file_path)] = "modified" if modified else "unchanged"
            except Exception as e:
                results[str(file_path)] = f"error: {e}"
        
        return results


# ============================================================
# 报告生成
# ============================================================

class ReportGenerator:
    """扫描报告生成器"""
    
    @staticmethod
    def generate_text_report(scan_results: dict, processor_results: dict = None) -> str:
        """生成文本报告"""
        lines = []
        lines.append("=" * 80)
        lines.append("TU-8 记忆宫殿 2.0 - 存量 .md 文件扫描报告")
        lines.append("=" * 80)
        lines.append(f"生成时间: {datetime.now(timezone.utc).isoformat()}")
        lines.append("")
        
        # 统计信息
        total_files = len(scan_results)
        total_findings = sum(len(findings) for findings in scan_results.values())
        high_risk_count = sum(
            1 for findings in scan_results.values()
            for _, _, desc, _ in findings
            if "[高风险]" in desc
        )
        medium_risk_count = total_findings - high_risk_count
        
        lines.append("【统计摘要】")
        lines.append(f"  扫描文件数: {total_files}")
        lines.append(f"  发现敏感信息数: {total_findings}")
        lines.append(f"    - 高风险: {high_risk_count}")
        lines.append(f"    - 中风险: {medium_risk_count}")
        lines.append("")
        
        # 处理结果
        if processor_results:
            modified_count = sum(1 for v in processor_results.values() if v == "modified")
            unchanged_count = sum(1 for v in processor_results.values() if v == "unchanged")
            error_count = sum(1 for v in processor_results.values() if v.startswith("error"))
            
            lines.append("【处理结果】")
            lines.append(f"  已处理: {modified_count + unchanged_count}")
            lines.append(f"    - 已脱敏: {modified_count}")
            lines.append(f"    - 无变化: {unchanged_count}")
            lines.append(f"  处理失败: {error_count}")
            lines.append("")
        
        # 详细发现
        lines.append("【详细发现】")
        lines.append("-" * 80)
        
        if not scan_results:
            lines.append("  未发现敏感信息")
        else:
            for file_path, findings in scan_results.items():
                lines.append(f"\n  📄 {file_path}")
                for line_content, pattern, description, line_num in findings:
                    lines.append(f"    行 {line_num}: {description}")
                    lines.append(f"      内容: {line_content[:80]}{'...' if len(line_content) > 80 else ''}")
        
        lines.append("")
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    @staticmethod
    def save_report(report: str, output_path: str = None):
        """保存报告"""
        if output_path is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            output_path = f"md_scan_report_{timestamp}.txt"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n[OK] 报告已保存: {output_path}")


# ============================================================
# 主程序
# ============================================================

def main():
    # 修复 Windows 控制台编码问题
    if sys.platform == 'win32':
        sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    import argparse
    
    parser = argparse.ArgumentParser(description="TU-8 存量 .md 文件扫描与脱敏")
    parser.add_argument("--scan", action="store_true", help="仅扫描，不脱敏")
    parser.add_argument("--process", action="store_true", help="执行脱敏（默认仅模拟）")
    parser.add_argument("--dry-run", action="store_true", default=True, help="模拟模式（默认开启）")
    parser.add_argument("--execute", action="store_true", help="实际执行脱敏（覆盖 dry-run）")
    parser.add_argument("--dir", type=str, help="指定扫描目录（覆盖配置）")
    parser.add_argument("--output", type=str, help="报告输出路径")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("TU-8 记忆宫殿 2.0 - 存量 .md 文件扫描与脱敏工具")
    print("=" * 80)
    
    # 确定扫描目录
    directories = [args.dir] if args.dir else SCAN_DIRECTORIES
    
    # 确定执行模式
    dry_run = not args.execute
    
    if dry_run:
        print("\n[INFO] 运行模式: 模拟（不实际修改文件）")
    else:
        print("\n[WARNING] 运行模式: 实际执行脱敏（不可逆！）")
        print("          建议先使用 --scan 模式预览结果")
    
    # Step 1: 扫描
    print("\n[1/3] 扫描敏感信息...")
    all_results = {}
    for directory in directories:
        print(f"\n  扫描目录: {directory}")
        results = SensitiveScanner.scan_directory(directory, recursive=True)
        if results:
            print(f"    发现 {len(results)} 个文件包含敏感信息")
            all_results.update(results)
        else:
            print(f"    未发现敏感信息")
    
    # Step 2: 生成报告
    print("\n[2/3] 生成扫描报告...")
    report = ReportGenerator.generate_text_report(all_results)
    print(report)
    
    # Step 3: 脱敏处理（可选）
    if args.scan:
        print("\n[3/3] 跳过脱敏处理（--scan 模式）")
    else:
        print(f"\n[3/3] {'模拟' if dry_run else '执行'}脱敏处理...")
        processor = MDProcessor(dry_run=dry_run)
        processor_results = {}
        
        for directory in directories:
            print(f"\n  处理目录: {directory}")
            results = processor.process_directory(directory, recursive=True)
            processor_results.update(results)
        
        # 生成最终报告
        final_report = ReportGenerator.generate_text_report(all_results, processor_results)
        
        # 保存报告
        if args.output:
            ReportGenerator.save_report(final_report, args.output)
        else:
            print("\n" + final_report)
    
    print("\n" + "=" * 80)
    print("扫描完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
