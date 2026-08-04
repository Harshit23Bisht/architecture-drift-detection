import json
import os
from typing import List, Dict

class DependencyResolver:
    def __init__(self, base_package: str):
        self.base_package = base_package
        self.edges = []

    def resolve_module_name(self, file_path: str, root_dir: str) -> str:
        """Converts a file path to a Python dotted module name."""
        rel_path = os.path.relpath(file_path, root_dir)
        module_path = rel_path.replace('.py', '').replace(os.sep, '.')
        if module_path.endswith('.__init__'):
            module_path = module_path[:-9]
        return f"{self.base_package}.{module_path}" if self.base_package else module_path

    def add_edges_from_ast(self, source_module: str, imports: List[Dict], calls: List[Dict]):
        """
        Maps imports and calls back to a concrete module name and creates dependency edges.
        """
        targets = set()
        
        for imp in imports:
            mod = imp.get("module")
            if mod:
                # Handle basic relative import resolution (MVP level)
                if mod.startswith('.'):
                    parts = source_module.split('.')
                    # Strip dots and resolve against parts
                    dots = len(mod) - len(mod.lstrip('.'))
                    base = parts[:-dots] if dots <= len(parts) else []
                    resolved = ".".join(base + [mod.lstrip('.')])
                    targets.add(resolved)
                else:
                    targets.add(mod)

        for target in targets:
            self.edges.append({
                "source": source_module,
                "target": target
            })

    def get_json_edges(self) -> str:
        """Serializes the final result as a clean JSON list."""
        # Deduplicate edges mathematically
        unique_edges = [dict(t) for t in {tuple(d.items()) for d in self.edges}]
        return json.dumps(unique_edges, indent=2)