import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from main import app
from engine.cli import evaluate_threshold, detect_git_changed_files, run_scan
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

# --- 7. CI SCAN GATE & INTEGRATION TESTS ---

def test_ci_normal_project_scan_passes(base_dir):
    """Verifies that normal scan of the actual project repository passes with exit code 0."""
    from types import SimpleNamespace
    args = SimpleNamespace(
        repo=str(base_dir),
        rules=str(base_dir / "architecture_rules.yaml"),
        fail_on="HIGH",
        save_history=False,
        ignore=None
    )

    exit_code = run_scan(args)
    assert exit_code == 0

def test_ci_intentional_sample_repo_violation_fails(base_dir):
    """Verifies that scanning sample_repo intentionally exits with code 1 due to HIGH violation."""
    from types import SimpleNamespace
    args = SimpleNamespace(
        repo=str(base_dir / "sample_repo"),
        rules=str(base_dir / "sample_repo" / "architecture_rules.yaml"),
        fail_on="HIGH",
        save_history=False,
        ignore=None
    )

    exit_code = run_scan(args)
    assert exit_code == 1

def test_ci_real_project_high_violation_fails(tmp_path):
    """Verifies that a real HIGH violation in a project fails the scanner with exit code 1."""
    repo = tmp_path / "violating_project"
    parser_dir = repo / "parser"
    parser_dir.mkdir(parents=True)
    (parser_dir / "__init__.py").write_text("")
    (parser_dir / "walker.py").write_text("import engine.pipeline\n")

    engine_dir = repo / "engine"
    engine_dir.mkdir(parents=True)
    (engine_dir / "__init__.py").write_text("")
    (engine_dir / "pipeline.py").write_text("class Pipeline: pass\n")

    rules_file = repo / "architecture_rules.yaml"
    rules_file.write_text("""
layers:
  - name: engine
    allowed_calls: [parser, engine]
  - name: parser
    allowed_calls: [parser]
    forbidden_calls: [engine]
ci:
  fail_on: HIGH
""")

    from types import SimpleNamespace
    args = SimpleNamespace(
        repo=str(repo),
        rules=str(rules_file),
        fail_on="HIGH",
        save_history=False,
        ignore=None
    )

    exit_code = run_scan(args)
    assert exit_code == 1

def test_ci_health_persistence_during_scan(base_dir, tmp_path):
    """Verifies that health score persistence continues working properly during scans."""
    db_file = tmp_path / "ci_history.db"
    storage = HealthHistoryStorage(db_path=str(db_file))

    pipeline = ArchitecturePipeline()
    result = pipeline.analyze(str(base_dir), str(base_dir / "architecture_rules.yaml"))
    run_id = storage.save_run(result, repo_name="project_root")

    assert run_id > 0
    history = storage.get_history(repo_name="project_root")
    assert len(history) == 1
    assert history[0]["health_score"] == 100
    assert history[0]["total_violations"] == 0
