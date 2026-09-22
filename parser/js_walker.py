from typing import List, Dict, Any
import tree_sitter
import tree_sitter_javascript as ts_js
from parser.base_walker import BaseAstWalker

class JavaScriptAstWalker(BaseAstWalker):
    """AST Walker adapter for JavaScript/TypeScript codebases using Tree-sitter."""

    def __init__(self):
        self.language = tree_sitter.Language(ts_js.language())
        self.parser = tree_sitter.Parser()
        self.parser.language = self.language

    def parse_file(self, content: bytes):
        return self.parser.parse(content)

    def _normalize_module_path(self, raw_path: str) -> str:
        clean = raw_path.replace("\\", "/").strip("./")
        for ext in [".js", ".jsx", ".ts", ".mjs"]:
            if clean.endswith(ext):
                clean = clean[:-len(ext)]
        parts = [p for p in clean.split("/") if p and p != ".."]
        return ".".join(parts)

    def extract_imports(self, root_node) -> List[Dict[str, Any]]:
        imports = []

        def traverse(node):
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "string":
                        raw_text = child.text.decode("utf-8").strip("'" + '"')
                        imports.append({
                            "module": self._normalize_module_path(raw_text),
                            "line": child.start_point[0] + 1
                        })

            elif node.type == "call_expression":
                fn_node = node.child_by_field_name("function")
                args_node = node.child_by_field_name("arguments")
                if fn_node and fn_node.text.decode("utf-8") == "require" and args_node:
                    for arg in args_node.children:
                        if arg.type == "string":
                            raw_text = arg.text.decode("utf-8").strip("'" + '"')
                            imports.append({
                                "module": self._normalize_module_path(raw_text),
                                "line": arg.start_point[0] + 1
                            })

            for child in node.children:
                traverse(child)

        traverse(root_node)
        return imports

    def extract_calls(self, root_node) -> List[Dict[str, Any]]:
        calls = []

        def traverse(node):
            if node.type == "call_expression":
                fn_node = node.child_by_field_name("function")
                if fn_node:
                    calls.append({
                        "call": fn_node.text.decode("utf-8"),
                        "line": fn_node.start_point[0] + 1
                    })

            for child in node.children:
                traverse(child)

        traverse(root_node)
        return calls