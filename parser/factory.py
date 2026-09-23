from pathlib import Path
from parser.base_walker import BaseAstWalker
from parser.ast_walker import PythonAstWalker
from parser.js_walker import JavaScriptAstWalker

class ParserFactory:
    """Selects the correct parser adapter based on file extension."""

    @staticmethod
    def get_walker(file_path: Path) -> BaseAstWalker:
        suffix = file_path.suffix.lower()
        if suffix == ".py":
            return PythonAstWalker()
        elif suffix in (".js", ".jsx", ".mjs", ".ts"):
            return JavaScriptAstWalker()
        else:
            raise ValueError(f"Unsupported file format: {suffix}")