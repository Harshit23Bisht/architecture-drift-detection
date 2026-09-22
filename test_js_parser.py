from pathlib import Path
from parser.js_walker import JavaScriptAstWalker

walker = JavaScriptAstWalker()
code = Path("sample_js_app/controller.js").read_bytes()
tree = walker.parse_file(code)

imports = walker.extract_imports(tree.root_node)
calls = walker.extract_calls(tree.root_node)

print("JS Imports:", imports)
print("JS Calls:", calls)