import ast
from typing import List, Dict, Any
from parser.base_walker import BaseAstWalker

class PythonAstWalker(BaseAstWalker):
    """AST Walker adapter for Python codebases using the standard ast library."""

    def parse_file(self, content: bytes):
        return ast.parse(content.decode("utf-8", errors="ignore"))

    def extract_imports(self, root_node) -> List[Dict[str, Any]]:
        imports = []
        for node in ast.walk(root_node):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({"module": alias.name, "line": node.lineno})
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append({"module": node.module, "line": node.lineno})
        return imports

    def extract_calls(self, root_node) -> List[Dict[str, Any]]:
        calls = []
        for node in ast.walk(root_node):
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                if func_name:
                    calls.append({"call": func_name, "line": node.lineno})
        return calls