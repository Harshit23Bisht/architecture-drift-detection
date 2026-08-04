import os
from pathlib import Path
from parser.ast_walker import PythonAstWalker
from parser.resolver import DependencyResolver

targets = ["requests", "flask", "fastapi"]

print("\n" + "="*60)
print("TESTING ARCHITECTURE DRIFT DETECTION ENGINE")
print("="*60)

walker = PythonAstWalker()

for name in targets:
    resolved_path = (Path("..") / name).resolve()
    
    if not resolved_path.exists():
        print(f"\n[ERROR] [{name.upper()}] Folder not found at {resolved_path}")
        continue
        
    print(f"\nScanning Codebase: {name.upper()}")
    print(f"Location: {resolved_path}")
    
    resolver = DependencyResolver(base_package=name)
    python_files = list(resolved_path.rglob("*.py"))
    parsed_count = 0
    total_imports = 0
    total_calls = 0
    
    for py_file in python_files:
        try:
            with open(py_file, "rb") as f:
                content = f.read()
                
            tree = walker.parse_file(content)
            imports = walker.extract_imports(tree.root_node)
            calls = walker.extract_calls(tree.root_node)
            
            source_module = resolver.resolve_module_name(str(py_file), str(resolved_path))
            resolver.add_edges_from_ast(source_module, imports, calls)
            
            parsed_count += 1
            total_imports += len(imports)
            total_calls += len(calls)
        except Exception as e:
            print(f"[WARNING] Error parsing {py_file.name}: {e}")
            
    print(f"[SUCCESS] Scanned without errors.")
    print(f"   Python Files Parsed: {parsed_count}")
    print(f"   Imports Extracted:   {total_imports}")
    print(f"   Calls Extracted:     {total_calls}")
    print(f"   Dependency Edges:    {len(resolver.edges)}")

print("\n" + "="*60 + "\n")
