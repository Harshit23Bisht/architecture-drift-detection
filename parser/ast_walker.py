import tree_sitter
import tree_sitter_python

class PythonAstWalker:
    def __init__(self):
        # Initialize the Tree-sitter Language
        self.language = tree_sitter.Language(tree_sitter_python.language())
        
        # Parser now accepts the language object directly 
        self.parser = tree_sitter.Parser(self.language)
        
        # Compile Tree-sitter queries 
        # FIX: We now accept either a dotted_name or relative_import or aliased_import
        self.import_query = tree_sitter.Query(self.language, """
            (import_statement name: [
                (dotted_name)
                (aliased_import)
            ] @import_name)
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

        self.def_query = tree_sitter.Query(self.language, """
            (function_definition name: (identifier) @func_def)
            (class_definition name: (identifier) @class_def)
        """)

    def parse_file(self, source_code: bytes):
        """Parses the raw source code bytes into a Tree-sitter AST."""
        return self.parser.parse(source_code)

    def extract_imports(self, root_node):
        """Extracts standard and relative imports from the AST with line numbers."""
        cursor = tree_sitter.QueryCursor(self.import_query)
        matches = cursor.matches(root_node)
        imports = []
        
        for match in matches:
            capture_dict = match[1]
            for capture_name, nodes in capture_dict.items():
                for node in nodes:
                    line = node.start_point[0] + 1
                    if capture_name == "import_name":
                        # If node is aliased_import, extract the inner dotted_name if available
                        if node.type == "aliased_import":
                            name_child = node.child_by_field_name("name")
                            text = name_child.text.decode('utf-8') if name_child else node.text.decode('utf-8')
                        else:
                            text = node.text.decode('utf-8')
                        imports.append({"type": "import", "module": text, "line": line})
                    elif capture_name == "module_name":
                        text = node.text.decode('utf-8')
                        imports.append({"type": "from_import_module", "module": text, "line": line})
                
        return imports

    def extract_calls(self, root_node):
        """Extracts function and method call sites using Tree-sitter queries with line numbers."""
        cursor = tree_sitter.QueryCursor(self.call_query)
        matches = cursor.matches(root_node)
        calls = []
        
        for match in matches:
            capture_dict = match[1]
            for capture_name, nodes in capture_dict.items():
                for node in nodes:
                    text = node.text.decode('utf-8')
                    line = node.start_point[0] + 1
                    if capture_name == "func_name":
                        calls.append({"type": "function_call", "name": text, "line": line})
                    elif capture_name == "obj_name":
                        calls.append({"type": "method_call_object", "name": text, "line": line})
                
        return calls

    def extract_definitions(self, root_node):
        """Extracts class and function definitions from the AST."""
        cursor = tree_sitter.QueryCursor(self.def_query)
        matches = cursor.matches(root_node)
        defs = []

        for match in matches:
            capture_dict = match[1]
            for capture_name, nodes in capture_dict.items():
                for node in nodes:
                    text = node.text.decode('utf-8')
                    line = node.start_point[0] + 1
                    if capture_name == "func_def":
                        defs.append({"type": "function", "name": text, "line": line})
                    elif capture_name == "class_def":
                        defs.append({"type": "class", "name": text, "line": line})

        return defs