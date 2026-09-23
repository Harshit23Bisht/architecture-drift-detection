from pathlib import Path
from parser.js_walker import JavaScriptAstWalker

def test_javascript_ast_parsing():
    target_path = Path("sample_js_app/controllers/userController.js")
    if not target_path.exists():
        target_path = Path("sample_js_app/controller.js")
    
    code = target_path.read_bytes()
    walker = JavaScriptAstWalker()
    tree = walker.parse_file(code)
    imports = walker.extract_imports(tree.root_node)

    assert len(imports) > 0, "Should have extracted at least one import from JS file"
    assert any("userRepository" in imp.get("module", "") or "repository" in imp.get("module", "") for imp in imports)
