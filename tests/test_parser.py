import pytest
from parser.ast_walker import PythonAstWalker
from parser.resolver import DependencyResolver
import json

@pytest.fixture
def ast_walker():
    return PythonAstWalker()

def test_extract_imports(ast_walker):
    source_code = b"""
import os
import sys
from myapp.services import user_service
from ..repository import db
    """
    tree = ast_walker.parse_file(source_code)
    imports = ast_walker.extract_imports(tree.root_node)
    
    modules = [imp["module"] for imp in imports if "module" in imp]
    assert "os" in modules
    assert "sys" in modules
    assert "myapp.services" in modules
    assert "..repository" in modules

def test_extract_calls(ast_walker):
    source_code = b"""
def handler():
    user_service.get_user()
    process_data()
    """
    tree = ast_walker.parse_file(source_code)
    calls = ast_walker.extract_calls(tree.root_node)
    
    call_names = [call["name"] for call in calls]
    assert "user_service" in call_names # Object of the method call
    assert "process_data" in call_names # Direct function call

def test_resolver_edges():
    resolver = DependencyResolver(base_package="myapp")
    
    source_module = "myapp.controllers.user_controller"
    mock_imports = [
        {"type": "import", "module": "os"},
        {"type": "from_import_module", "module": "..services.user_service"}
    ]
    mock_calls = [] # Calls aren't actively resolving edges in simple MVP state
    
    resolver.add_edges_from_ast(source_module, mock_imports, mock_calls)
    edges_json = resolver.get_json_edges()
    edges = json.loads(edges_json)
    
    assert len(edges) == 2
    # Standard import
    assert {"source": "myapp.controllers.user_controller", "target": "os"} in edges
    # Relative import resolution: myapp.controllers minus 2 levels -> myapp + services.user_service
    assert {"source": "myapp.controllers.user_controller", "target": "myapp.services.user_service"} in edges

def test_yaml_schema_validation():
    from rules.schema import ArchitectureConfig, LayerRule
    from pydantic import ValidationError
    
    # Valid config
    valid_data = {
        "layers": [
            {"name": "Controller", "allowed_calls": ["Service"]},
            {"name": "Service", "allowed_calls": ["Repository"]},
            {"name": "Repository", "allowed_calls": []}
        ]
    }
    config = ArchitectureConfig(**valid_data)
    assert len(config.layers) == 3
    
    # Invalid config (references non-existent layer)
    invalid_data = {
        "layers": [
            {"name": "Controller", "allowed_calls": ["NonExistentLayer"]}
        ]
    }
    with pytest.raises(ValidationError):
        ArchitectureConfig(**invalid_data)