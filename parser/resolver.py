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

    def is_internal_module(self, target: str, known_modules: set = None) -> bool:
        """Determines if a target module is internal to the analyzed codebase."""
        if known_modules and target in known_modules:
            return True
        if self.base_package and (target == self.base_package or target.startswith(self.base_package + ".")):
            return True
        return False

    def add_edges_from_ast(self, source_module: str, imports: List[Dict], calls: List[Dict], known_modules: set = None):
        """
        Maps imports and calls back to a concrete module name and creates dependency edges with location metadata.
        """
        seen = set()

        for imp in imports:
            mod = imp.get("module")
            line = imp.get("line")
            if not mod:
                continue

            if mod.startswith('.'):
                parts = source_module.split('.')
                dots = len(mod) - len(mod.lstrip('.'))
                base = parts[:-dots] if dots <= len(parts) else []
                remainder = mod.lstrip('.')
                target = ".".join(base + ([remainder] if remainder else []))
            else:
                target = mod

            edge_key = (source_module, target)
            if edge_key not in seen:
                seen.add(edge_key)
                is_internal = self.is_internal_module(target, known_modules)
                self.edges.append({
                    "source": source_module,
                    "target": target,
                    "line": line,
                    "is_internal": is_internal,
                    "kind": imp.get("type", "import")
                })

        # Process call sites if they reference known module names or objects
        for call in calls:
            call_name = call.get("name")
            line = call.get("line")
            if not call_name:
                continue

            # If call_name matches a known module or package target, add edge
            if known_modules and call_name in known_modules:
                edge_key = (source_module, call_name)
                if edge_key not in seen:
                    seen.add(edge_key)
                    self.edges.append({
                        "source": source_module,
                        "target": call_name,
                        "line": line,
                        "is_internal": True,
                        "kind": call.get("type", "call")
                    })

    def get_json_edges(self) -> str:
        """Serializes the final result as a clean JSON list of source/target dicts."""
        basic_edges = [{"source": e["source"], "target": e["target"]} for e in self.edges]
        # Deduplicate basic edges
        unique_edges = [dict(t) for t in {tuple(d.items()) for d in basic_edges}]
        return json.dumps(unique_edges, indent=2)

    def get_detailed_edges(self) -> List[Dict]:
        """Returns the full list of edge dictionaries including location and internal flags."""
        return self.edges
