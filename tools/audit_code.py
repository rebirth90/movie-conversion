import ast
import os

from pathlib import Path
from collections import defaultdict

class CodeAuditor:
    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)
        self.python_files = self._get_python_files()
        
        # Tracking
        self.global_definitions = defaultdict(list) # name -> [(file, lineno)]
        self.global_usages = set()
        self.file_unused_imports = defaultdict(list)

    def _get_python_files(self):
        # Exclude hidden, tests, tools
        return [p for p in self.root_dir.rglob("*.py") 
                if not any(part.startswith('.') for part in p.parts)
                and 'tests' not in p.parts 
                and 'tools' not in p.parts
                and 'venv' not in p.parts]

    def scan(self):
        for file_path in self.python_files:
            self._analyze_file(file_path)
            
        self._report()

    def _analyze_file(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
            except Exception as e:
                print(f"Skipping {file_path}: {e}")
                return

        # Local analysis for imports
        imports = {}
        local_usages = set()
        definitions = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    name = alias.asname or alias.name
                    # If it's a dotted import (e.g. os.path), we track 'os'
                    root_name = name.split('.')[0]
                    imports[root_name] = (alias.name, node.lineno)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                if not node.name.startswith('_'): # Skip privates
                    definitions.append((node.name, node.lineno))
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    local_usages.add(node.id)
            elif isinstance(node, ast.Attribute):
                local_usages.add(node.attr) # usage of attribute name

        # Filter unused imports
        for name, (module, lineno) in imports.items():
            if name not in local_usages:
                # Special cases
                if name in ['sys', 'os']: continue # often used implicitly or valid to keep
                self.file_unused_imports[file_path].append((module, lineno))

        # Update global stats
        for def_name, lineno in definitions:
            self.global_definitions[def_name].append((file_path, lineno))
        
        self.global_usages.update(local_usages)

    def _report(self):
        print("=== UNUSED IMPORTS ===")
        for path, unused in self.file_unused_imports.items():
            if unused:
                print(f"\n[{path.name}]")
                for mod, line in unused:
                    print(f"  Line {line}: {mod}")

        print("\n=== POTENTIALLY UNUSED FUNCTIONS/CLASSES ===")
        for name, locations in self.global_definitions.items():
            if name not in self.global_usages and name != 'main':
                # Skip __init__, common overrides
                if name in ['__init__', 'setUp', 'tearDown', 'run']: continue
                
                for path, line in locations:
                    print(f"  {name} (Line {line}) in {path.name}")

if __name__ == "__main__":
    auditor = CodeAuditor(os.getcwd())
    auditor.scan()
