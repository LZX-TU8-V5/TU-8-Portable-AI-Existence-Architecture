#!/usr/bin/env python3
"""
TU-8 Module Reference Analysis Tool
Scan all Python files in src/ directory for import statements, generate reference matrix
"""
import os
import re
import json
from pathlib import Path
from collections import defaultdict
def analyze_imports(src_dir: str) -> dict:
    """
    Analyze import statements in all Python files in the specified directory
    
    Returns:
        {
            "module_name": {
                "imports": ["module1", "module2", ...],
                "imported_by": ["moduleA", "moduleB", ...]
            }
        }
    """
    src_path = Path(src_dir)
    if not src_path.exists():
        raise FileNotFoundError(f"Directory not found: {src_dir}")
    
    # Storage
    module_imports = defaultdict(set)  # module -> modules it imports
    module_imported_by = defaultdict(set)  # module -> modules that import it
    
    # Scan all .py files
    py_files = list(src_path.glob("*.py"))
    
    for py_file in py_files:
        module_name = py_file.stem  # Remove .py extension
        
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Use regex to match import statements
            # Match: import xxx, from xxx import yyy
            import_patterns = [
                r"^\s*import\s+([\w\.]+)",  # import xxx
                r"^\s*from\s+([\w\.]+)\s+import",  # from xxx import
            ]
            
            imports = set()
            for pattern in import_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                for match in matches:
                    # Only care about modules in src/ directory (ignore stdlib and third-party)
                    if match.startswith("src.") or match in [f.stem for f in py_files]:
                        module_imported = match.replace("src.", "")
                        imports.add(module_imported)
            
            # Store results
            module_imports[module_name] = imports
            
        except Exception as e:
            print(f"[WARNING] Cannot analyze {py_file.name}: {e}")
    
    # Build reverse reference (imported_by)
    for module, imports in module_imports.items():
        for imported in imports:
            module_imported_by[imported].add(module)
    
    # Convert to serializable format
    result = {}
    for module in set(list(module_imports.keys()) + list(module_imported_by.keys())):
        result[module] = {
            "imports": sorted(list(module_imports.get(module, set()))),
            "imported_by": sorted(list(module_imported_by.get(module, set())))
        }
    
    return result
def generate_matrix(import_data: dict) -> list:
    """
    Generate reference matrix (Markdown table format)
    """
    modules = sorted(import_data.keys())
    
    # Header
    matrix = []
    matrix.append(["Module"] + modules)
    
    # Each row
    for module in modules:
        row = [module]
        for other in modules:
            if other in import_data[module]["imports"]:
                row.append("X")
            else:
                row.append("")
        matrix.append(row)
    
    return matrix
def main():
    # Get workspace directory (parent of scripts directory)
    script_dir = Path(__file__).parent
    workspace_dir = script_dir.parent
    src_dir = workspace_dir / "src"
    
    print("[analyze_imports.py] TU-8 Module Reference Analysis")
    print("=" * 60)
    
    try:
        # Analyze import statements
        import_data = analyze_imports(str(src_dir))
        
        # Generate matrix
        matrix = generate_matrix(import_data)
        
        # Output to console
        print("\n[Matrix] Module Reference Matrix:")
        print("-" * 60)
        
        # Calculate column width
        col_width = max(len(module) for module in import_data.keys()) + 2
        col_width = min(col_width, 20)  # Max width 20
        
        # Print header
        header = matrix[0]
        print(header[0].ljust(col_width), end="")
        for cell in header[1:]:
            print(cell.ljust(col_width), end="")
        print()
        
        # Print separator
        print("-" * (col_width * (len(header))))
        
        # Print each row
        for row in matrix[1:]:
            print(row[0].ljust(col_width), end="")
            for cell in row[1:]:
                print(cell.ljust(col_width), end="")
            print()
        
        # Save as JSON
        output_file = workspace_dir / "docs" / "module_references.json"
        os.makedirs(output_file.parent, exist_ok=True)
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(import_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Reference data saved to: {output_file}")
        
        # Save as Markdown table
        md_file = workspace_dir / "docs" / "../knowledge_base/knowledge/02_IMPLEMENTATION/../knowledge_base/knowledge/02_IMPLEMENTATION/module_references.md"
        
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("# TU-8 Module Reference Matrix\n\n")
            f.write("| " + " | ".join(matrix[0]) + " |\n")
            f.write("|" + "|".join(["---"] * len(matrix[0])) + "|\n")
            
            for row in matrix[1:]:
                # Shorten module names (use ... if > 15 chars)
                short_row = [cell[:15] + "..." if len(cell) > 15 else cell for cell in row]
                f.write("| " + " | ".join(short_row) + " |\n")
        
        print(f"[OK] Markdown table saved to: {md_file}")
        
        # Print statistics
        print("\n[Statistics] Statistics:")
        print("-" * 60)
        
        total_modules = len(import_data)
        total_refs = sum(len(data["imports"]) for data in import_data.values())
        avg_refs = total_refs / total_modules if total_modules > 0 else 0
        
        print(f"Total modules: {total_modules}")
        print(f"Total references: {total_refs}")
        print(f"Average references per module: {avg_refs:.2f}")
        
        # Find most imported modules
        most_imported = sorted(
            [(m, len(d["imported_by"])) for m, d in import_data.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        print(f"\n[Top 5] Most Imported Modules:")
        for module, count in most_imported:
            print(f"  {module}: {count} imports")
        
        # Find modules with most imports
        most_imports = sorted(
            [(m, len(d["imports"])) for m, d in import_data.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        print(f"\n[Top 5] Modules with Most Imports:")
        for module, count in most_imports:
            print(f"  {module}: imports {count} modules")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        return 1
    
    return 0
if __name__ == "__main__":
    exit(main())
