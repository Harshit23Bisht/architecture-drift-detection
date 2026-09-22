import os
import pytest
import networkx as nx
from pathlib import Path

from rules.schema import ArchitectureConfig, LayerRule, load_config
from parser.ast_walker import PythonAstWalker
from parser.resolver import DependencyResolver
from engine.graph_builder import GraphBuilder
from engine.rule_engine import RuleEngine
from engine.scorer import SeverityScorer
from engine.pipeline import ArchitecturePipeline

@pytest.fixture
def base_dir():
    return Path(__file__).parent.parent.resolve()

@pytest.fixture
def mock_layers():
    return [
        LayerRule(name="Controller", allowed_calls=["Service"], forbidden_calls=["Repository"]),
        LayerRule(name="Service", allowed_calls=["Repository"]),
        LayerRule(name="Repository", allowed_calls=[])
    ]

# --- 1. ARCHITECTURE LAYER MATCHING TESTS ---

def test_layer_matching_exact(mock_layers):
    engine = RuleEngine(configured_layers=mock_layers)
    assert engine._get_layer_for_module("myapp.controllers.auth") == "Controller"
    assert engine._get_layer_for_module("myapp.services.user") == "Service"
    assert engine._get_layer_for_module("myapp.repository.db") == "Repository"

def test_layer_matching_nested_packages(mock_layers):
    engine = RuleEngine(configured_layers=mock_layers)
    assert engine._get_layer_for_module("myapp.admin.controllers.user_controller") == "Controller"
    assert engine._get_layer_for_module("company.project.services.auth_service") == "Service"

def test_layer_matching_similar_names_no_false_positive(mock_layers):
    engine = RuleEngine(configured_layers=mock_layers)
    # controller_helper should NOT match Controller because it's a different segment
    assert engine._get_layer_for_module("myapp.services.controller_helper") == "Service"
    # microservice should NOT match Service
    assert engine._get_layer_for_module("myapp.utils.microservice") is None

def test_layer_matching_unmatched_files(mock_layers):
    engine = RuleEngine(configured_layers=mock_layers)
    assert engine._get_layer_for_module("myapp.utils.helpers") is None
    assert engine._get_layer_for_module("test_main") is None
    assert engine._get_layer_for_module("") is None

# --- 2. FORBIDDEN CALL RULES TESTS ---

def test_forbidden_call_violation_generated(mock_layers):
    engine = RuleEngine(configured_layers=mock_layers)
    graph = nx.DiGraph()
    graph.add_edge("myapp.controllers.auth", "myapp.repository.user")

    violations = engine.detect_violations(graph, edge_metadata={("myapp.controllers.auth", "myapp.repository.user"): {"line": 15}})
    assert len(violations) == 1
    v = violations[0]
    assert v["violation_type"] == "layer_violation"
    assert "explicitly forbidden" in v["rule_broken"]
    assert v["line"] == 15
    assert v["source_layer"] == "Controller"
    assert v["target_layer"] == "Repository"

def test_permitted_call_no_violation(mock_layers):
    engine = RuleEngine(configured_layers=mock_layers)
    graph = nx.DiGraph()
    graph.add_edge("myapp.controllers.auth", "myapp.services.auth")

    violations = engine.detect_violations(graph)
    assert len(violations) == 0

def test_wildcard_forbidden_call():
    layers = [
        LayerRule(name="Domain", allowed_calls=[], forbidden_calls=["*"]),
        LayerRule(name="Service", allowed_calls=["Domain"])
    ]
    engine = RuleEngine(configured_layers=layers)
    graph = nx.DiGraph()
    graph.add_edge("myapp.domain.model", "myapp.services.user")

    violations = engine.detect_violations(graph)
    assert len(violations) == 1
    assert "explicitly forbidden" in violations[0]["rule_broken"]

# --- 3. IMPORT AND DEPENDENCY EXTRACTION TESTS ---

def test_ast_walker_import_patterns():
    walker = PythonAstWalker()
    code = b"""
import os, sys
import myapp.repository.db as db_module
from myapp.services.auth import login, logout
from ..repository.user import UserRepository
    """
    tree = walker.parse_file(code)
    imports = walker.extract_imports(tree.root_node)

    modules = [imp["module"] for imp in imports]
    assert "os" in modules
    assert "sys" in modules
    assert "myapp.repository.db" in modules
    assert "myapp.services.auth" in modules
    assert "..repository.user" in modules

def test_resolver_internal_vs_external():
    resolver = DependencyResolver(base_package="myapp")
    known = {"myapp.services.auth", "myapp.repository.db"}

    assert resolver.is_internal_module("myapp.services.auth", known) is True
    assert resolver.is_internal_module("os", known) is False
    assert resolver.is_internal_module("requests", known) is False

def test_resolver_add_edges_with_locations():
    resolver = DependencyResolver(base_package="myapp")
    imports = [
        {"type": "import", "module": "os", "line": 1},
        {"type": "from_import_module", "module": "myapp.services.auth", "line": 5}
    ]
    resolver.add_edges_from_ast("myapp.controllers.user", imports, calls=[], known_modules={"myapp.services.auth"})

    detailed = resolver.get_detailed_edges()
    assert len(detailed) == 2
    
    auth_edge = next(e for e in detailed if e["target"] == "myapp.services.auth")
    assert auth_edge["line"] == 5
    assert auth_edge["is_internal"] is True

    os_edge = next(e for e in detailed if e["target"] == "os")
    assert os_edge["line"] == 1
    assert os_edge["is_internal"] is False

# --- 4. SEVERITY & RESULTS DEDUPLICATION TESTS ---

def test_violation_deduplication(mock_layers):
    engine = RuleEngine(configured_layers=mock_layers)
    graph = nx.DiGraph()
    # Adding duplicate edge attempts
    graph.add_edge("myapp.controllers.auth", "myapp.repository.user")
    graph.add_edge("myapp.controllers.auth", "myapp.repository.user")

    violations = engine.detect_violations(graph)
    assert len(violations) == 1

def test_severity_scoring_determinism():
    violation = {"violation_type": "layer_violation", "edge_or_cycle": ["A", "B"]}
    scored1 = SeverityScorer.score_violation(dict(violation))
    scored2 = SeverityScorer.score_violation(dict(violation))

    assert scored1["severity"] == scored2["severity"] == "high"
    assert scored1["impact_score"] == scored2["impact_score"] == 85

# --- 5. ERROR HANDLING TESTS ---

def test_load_config_malformed_yaml(tmp_path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("layers: [this is invalid yaml: {")

    with pytest.raises(ValueError, match="Malformed YAML syntax"):
        load_config(str(bad_yaml))

def test_load_config_invalid_dict(tmp_path):
    bad_yaml = tmp_path / "list.yaml"
    bad_yaml.write_text("- item1\n- item2")

    with pytest.raises(ValueError, match="Root content must be a dictionary"):
        load_config(str(bad_yaml))

def test_pipeline_empty_repository(tmp_path, base_dir):
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    rules_file = base_dir / "sample_repo" / "architecture_rules.yaml"

    pipeline = ArchitecturePipeline()
    result = pipeline.analyze(str(empty_repo), str(rules_file))

    assert "error" not in result
    assert result["parsed_file_count"] == 0
    assert result["total_dependencies"] == 0
    assert len(result["violations"]) == 0
    assert result["health_score"] == 100
    assert result["status"] == "Healthy"

def test_pipeline_syntax_error_handling(tmp_path, base_dir):
    repo = tmp_path / "repo_with_syntax_error"
    repo.mkdir()
    bad_py = repo / "bad_file.py"
    bad_py.write_text("def unclosed_function(:\n    pass bad syntax $$$")
    rules_file = base_dir / "sample_repo" / "architecture_rules.yaml"

    pipeline = ArchitecturePipeline()
    result = pipeline.analyze(str(repo), str(rules_file))

    assert "error" not in result
    assert result["parsed_file_count"] == 1

# --- 6. REAL REPOSITORY VALIDATION SCANS ---

def test_full_pipeline_valid_repo_scan(base_dir):
    valid_repo = base_dir / "sample_repo_valid"
    rules_file = valid_repo / "architecture_rules.yaml"

    pipeline = ArchitecturePipeline()
    result = pipeline.analyze(str(valid_repo), str(rules_file))

    assert "error" not in result
    assert result["parsed_file_count"] >= 4
    assert len(result["violations"]) == 0
    assert result["health_score"] == 100
    assert result["status"] == "Healthy"
    assert result["summary"]["total_violations"] == 0

def test_full_pipeline_violating_repo_scan(base_dir):
    violating_repo = base_dir / "sample_repo"
    rules_file = violating_repo / "architecture_rules.yaml"

    pipeline = ArchitecturePipeline()
    result = pipeline.analyze(str(violating_repo), str(rules_file))

    assert "error" not in result
    assert result["parsed_file_count"] >= 4
    assert len(result["violations"]) == 2
    assert result["health_score"] == 0
    assert result["status"] == "Critical"
    assert result["summary"]["total_violations"] == 2
