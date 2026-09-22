import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from main import app
from engine.cli import evaluate_threshold, detect_git_changed_files
from engine.storage import HealthHistoryStorage
from engine.pipeline import ArchitecturePipeline
from rules.schema import CIConfig, ArchitectureConfig, LayerRule

client = TestClient(app)

@pytest.fixture
def base_dir():
    return Path(__file__).parent.parent.resolve()

@pytest.fixture
def temp_storage(tmp_path):
    db_file = tmp_path / "test_history.db"
    return HealthHistoryStorage(db_path=str(db_file))

# --- 1. SEVERITY THRESHOLD TESTS ---

def test_evaluate_threshold_high():
    high_viol = [{"severity": "HIGH", "violation_type": "layer_violation"}]
    med_viol = [{"severity": "MEDIUM", "violation_type": "layer_violation"}]
    low_viol = [{"severity": "LOW", "violation_type": "layer_violation"}]

    # fail_on HIGH: only HIGH triggers failure
    assert evaluate_threshold(high_viol, "HIGH") is True
    assert evaluate_threshold(med_viol, "HIGH") is False
    assert evaluate_threshold(low_viol, "HIGH") is False

def test_evaluate_threshold_medium():
    high_viol = [{"severity": "HIGH"}]
    med_viol = [{"severity": "MEDIUM"}]
    low_viol = [{"severity": "LOW"}]

    # fail_on MEDIUM: HIGH and MEDIUM trigger failure
    assert evaluate_threshold(high_viol, "MEDIUM") is True
    assert evaluate_threshold(med_viol, "MEDIUM") is True
    assert evaluate_threshold(low_viol, "MEDIUM") is False

def test_evaluate_threshold_low():
    high_viol = [{"severity": "HIGH"}]
    med_viol = [{"severity": "MEDIUM"}]
    low_viol = [{"severity": "LOW"}]

    # fail_on LOW: ALL severities trigger failure
    assert evaluate_threshold(high_viol, "LOW") is True
    assert evaluate_threshold(med_viol, "LOW") is True
    assert evaluate_threshold(low_viol, "LOW") is True

# --- 2. CONFIG SCHEMA CI BLOCK TESTS ---

def test_ci_config_schema():
    ci = CIConfig(fail_on="medium")
    assert ci.fail_on == "MEDIUM"

    with pytest.raises(ValueError):
        CIConfig(fail_on="INVALID_SEVERITY")

# --- 3. SQLITE PERSISTENCE STORAGE TESTS ---

def test_storage_save_and_retrieve(temp_storage):
    mock_result = {
        "target_repository": "/projects/test_repo",
        "health_score": 85,
        "parsed_file_count": 10,
        "total_dependencies": 15,
        "violations": [
            {"severity": "HIGH", "violation_type": "layer_violation"},
            {"severity": "MEDIUM", "violation_type": "circular_dependency"}
        ]
    }

    run_id = temp_storage.save_run(mock_result, commit_sha="abc12345", repo_name="test_repo")
    assert run_id > 0

    history = temp_storage.get_history()
    assert len(history) == 1
    record = history[0]

    assert record["repo_name"] == "test_repo"
    assert record["commit_sha"] == "abc12345"
    assert record["health_score"] == 85
    assert record["total_violations"] == 2
    assert record["high_count"] == 1
    assert record["medium_count"] == 1
    assert record["low_count"] == 0

def test_storage_filtering_and_multiple_runs(temp_storage):
    mock1 = {"target_repository": "/repo_a", "health_score": 100, "violations": []}
    mock2 = {"target_repository": "/repo_b", "health_score": 50, "violations": [{"severity": "HIGH"}]}

    temp_storage.save_run(mock1, repo_name="repo_a")
    temp_storage.save_run(mock2, repo_name="repo_b")

    all_history = temp_storage.get_history()
    assert len(all_history) == 2

    repo_a_history = temp_storage.get_history(repo_name="repo_a")
    assert len(repo_a_history) == 1
    assert repo_a_history[0]["repo_name"] == "repo_a"

# --- 4. FASTAPI HEALTH HISTORY API ENDPOINTS ---

def test_api_health_history_endpoint():
    response = client.get("/health-history")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_api_health_history_repo_filter():
    response = client.get("/health-history/sample_repo")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

# --- 5. GIT CHANGED FILES DETECTION ---

def test_git_changed_files_detection(base_dir):
    files = detect_git_changed_files(str(base_dir))
    assert isinstance(files, list)

# --- 6. OFFLINE CI SCANS WITHOUT LLM API KEY ---

def test_ci_offline_mode_resiliency(base_dir):
    old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        sample_repo = base_dir / "sample_repo"
        sample_rules = sample_repo / "architecture_rules.yaml"

        pipeline = ArchitecturePipeline()
        result = pipeline.analyze(str(sample_repo), str(sample_rules))

        assert result["status"] == "Critical"
        assert len(result["violations"]) > 0
        # Ensure offline fallback text is present
        assert "LLM API key not found" in result["violations"][0]["ai_explanation"] or "Failed to contact LLM" in result["violations"][0]["ai_explanation"]
    finally:
        if old_key:
            os.environ["ANTHROPIC_API_KEY"] = old_key
