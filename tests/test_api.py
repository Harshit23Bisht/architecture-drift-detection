import pytest
from fastapi.testclient import TestClient
from main import app
from engine.scorer import SeverityScorer

client = TestClient(app)

def test_get_graph_endpoint():
    response = client.get("/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) > 0

def test_get_violations_endpoint():
    response = client.get("/violations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    if len(data) > 0:
        violation = data[0]
        assert "severity" in violation
        assert "ai_explanation" in violation
        assert "ai_fix" in violation

def test_health_score_endpoint():
    response = client.get("/health-score")
    assert response.status_code == 200
    data = response.json()
    assert "health_score" in data
    assert "status" in data
    assert isinstance(data["health_score"], int)

def test_scorer_logic():
    mock_violation = {
        "violation_type": "layer_violation",
        "edge_or_cycle": ["A", "B"]
    }
    scored = SeverityScorer.score_violation(mock_violation)
    assert scored["severity"] == "high"
    assert scored["impact_score"] == 85