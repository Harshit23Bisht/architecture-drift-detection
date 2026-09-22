import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
from engine.scorer import SeverityScorer

client = TestClient(app)

@pytest.fixture
def sample_repo_paths():
    base_dir = Path(__file__).parent.parent.resolve()
    repo_path = base_dir / "sample_repo"
    rules_path = repo_path / "architecture_rules.yaml"
    return str(repo_path), str(rules_path)

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

def test_post_analyze_endpoint_default():
    response = client.post("/analyze", json={})
    assert response.status_code == 200
    data = response.json()
    assert "health_score" in data
    assert "violations" in data
    assert "nodes" in data
    assert "links" in data
    assert data["parsed_file_count"] >= 4

def test_post_analyze_endpoint_custom_repo(sample_repo_paths):
    repo_path, rules_path = sample_repo_paths
    response = client.post("/analyze", json={"repo_path": repo_path, "rules_path": rules_path})
    assert response.status_code == 200
    data = response.json()
    assert data["target_repository"] == repo_path
    assert len(data["violations"]) >= 2

def test_post_analyze_endpoint_invalid_repo(sample_repo_paths):
    _, rules_path = sample_repo_paths
    response = client.post("/analyze", json={"repo_path": "/invalid/non_existent_directory_xyz", "rules_path": rules_path})
    assert response.status_code == 400
    assert "Invalid repository path" in response.json()["detail"]

def test_post_analyze_endpoint_invalid_rules(sample_repo_paths):
    repo_path, _ = sample_repo_paths
    response = client.post("/analyze", json={"repo_path": repo_path, "rules_path": "/invalid/missing_rules.yaml"})
    assert response.status_code == 400
    assert "Rules file not found" in response.json()["detail"]

def test_scorer_logic():
    mock_violation = {
        "violation_type": "layer_violation",
        "edge_or_cycle": ["A", "B"]
    }
    scored = SeverityScorer.score_violation(mock_violation)
    assert scored["severity"] == "high"
    assert scored["impact_score"] == 85