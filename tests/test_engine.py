import pytest
import networkx as nx
from engine.graph_builder import GraphBuilder
from engine.rule_engine import RuleEngine

# A simple mock object to represent the Pydantic LayerRule from Chunk 1
class MockLayerRule:
    def __init__(self, name: str, allowed_calls: list):
        self.name = name
        self.allowed_calls = allowed_calls

@pytest.fixture
def mock_layers():
    """Defines a strict layered architecture: Controller -> Service -> Repository."""
    return [
        MockLayerRule(name="Controller", allowed_calls=["Service"]),
        MockLayerRule(name="Service", allowed_calls=["Repository"]),
        MockLayerRule(name="Repository", allowed_calls=[])
    ]

@pytest.fixture
def rule_engine(mock_layers):
    return RuleEngine(configured_layers=mock_layers)

def test_graph_builder():
    edges = [
        {"source": "myapp.controllers.user", "target": "myapp.services.user"},
        {"source": "myapp.services.user", "target": "myapp.repository.db"}
    ]
    graph = GraphBuilder.build_from_edges(edges)
    
    assert isinstance(graph, nx.DiGraph)
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2
    assert graph.has_edge("myapp.controllers.user", "myapp.services.user")

def test_rule_engine_valid_architecture(rule_engine):
    """Tests that a clean architecture produces 0 violations."""
    graph = nx.DiGraph()
    graph.add_edge("myapp.controllers.auth", "myapp.services.auth")
    graph.add_edge("myapp.services.auth", "myapp.repository.user")

    violations = rule_engine.detect_violations(graph)
    assert len(violations) == 0

def test_rule_engine_layer_violation(rule_engine):
    """Tests detection of a Controller bypassing the Service to call the Repository[cite: 2]."""
    graph = nx.DiGraph()
    # Valid call
    graph.add_edge("myapp.controllers.auth", "myapp.services.auth")
    # Invalid call (Skip violation)
    graph.add_edge("myapp.controllers.auth", "myapp.repository.user")

    violations = rule_engine.detect_violations(graph)
    
    assert len(violations) == 1
    violation = violations[0]
    assert violation["violation_type"] == "layer_violation"
    assert violation["edge_or_cycle"] == ["myapp.controllers.auth", "myapp.repository.user"]
    assert "not allowed to call" in violation["rule_broken"]

def test_rule_engine_circular_dependency(rule_engine):
    """Tests detection of a circular dependency cycle[cite: 2]."""
    graph = nx.DiGraph()
    # Service A calls Service B, but Service B calls Service A back
    graph.add_edge("myapp.services.a", "myapp.services.b")
    graph.add_edge("myapp.services.b", "myapp.services.a")

    violations = rule_engine.detect_violations(graph)
    
    # We should have 1 circular dependency violation
    cycle_violations = [v for v in violations if v["violation_type"] == "circular_dependency"]
    assert len(cycle_violations) == 1
    
    violation = cycle_violations[0]
    assert "myapp.services.a" in violation["edge_or_cycle"]
    assert "myapp.services.b" in violation["edge_or_cycle"]