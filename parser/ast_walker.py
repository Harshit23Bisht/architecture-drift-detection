import tree_sitter
import tree_sitter_python

class PythonAstWalker:
    def __init__(self):
        # Initialize the Tree-sitter Language
        self.language = tree_sitter.Language(tree_sitter_python.language())
        
        # Parser now accepts the language object directly 
        self.parser = tree_sitter.Parser(self.language)
        
        # Compile Tree-sitter queries 
        # FIX: We now accept either a dotted_name or relative_import for the module_name
        self.import_query = tree_sitter.Query(self.language, """
            (import_statement name: (dotted_name) @import_name)
            (import_from_statement 
                module_name: [
                    (dotted_name)
                    (relative_import)
                ] @module_name)
        """)
        
        self.call_query = tree_sitter.Query(self.language, """
            (call function: (identifier) @func_name)
            (call function: (attribute object: (identifier) @obj_name attribute: (identifier) @attr_name))
        """)

    def parse_file(self, source_code: bytes):
        """Parses the raw source code bytes into a Tree-sitter AST."""
        return self.parser.parse(source_code)

    def extract_imports(self, root_node):
        """Extracts standard and relative imports from the AST."""
        cursor = tree_sitter.QueryCursor(self.import_query)
        matches = cursor.matches(root_node)
        imports = []
        
        for match in matches:
            capture_dict = match[1]
            for capture_name, nodes in capture_dict.items():
                for node in nodes:
                    text = node.text.decode('utf-8')
                    if capture_name == "import_name":
                        imports.append({"type": "import", "module": text})
                    elif capture_name == "module_name":
                        imports.append({"type": "from_import_module", "module": text})
                
        return imports

    def extract_calls(self, root_node):
        """Extracts function and method call sites using Tree-sitter queries."""
        cursor = tree_sitter.QueryCursor(self.call_query)
        matches = cursor.matches(root_node)
        calls = []
        
        for match in matches:
            capture_dict = match[1]
            for capture_name, nodes in capture_dict.items():
                for node in nodes:
                    text = node.text.decode('utf-8')
                    if capture_name == "func_name":
                        calls.append({"type": "function_call", "name": text})
                    elif capture_name == "obj_name":
                        calls.append({"type": "method_call_object", "name": text})
                
        return calls