import os
import pytest
from pathlib import Path
from engine.pipeline import ArchitecturePipeline

@pytest.fixture
def sample_repo_paths():
    base_dir = Path(__file__).parent.parent.resolve()
    repo_path = base_dir / "sample_repo"
    rules_path = repo_path / "architecture_rules.yaml"
    return str(repo_path), str(rules_path)

def test_pipeline_sample_repo_analysis(sample_repo_paths):
    repo_path, rules_path = sample_repo_paths
    pipeline = ArchitecturePipeline()
    result = pipeline.analyze(repo_path, rules_path)

    assert "error" not in result
    assert result["parsed_file_count"] >= 4
    assert result["total_dependencies"] > 0
    assert len(result["violations"]) >= 2

    # Check layer violation detection
    layer_viols = [v for v in result["violations"] if v["violation_type"] == "layer_violation"]
    assert len(layer_viols) >= 1
    assert layer_viols[0]["severity"] == "high"
    assert "ai_explanation" in layer_viols[0]
    assert "ai_fix" in layer_viols[0]

    # Check circular dependency detection
    cycle_viols = [v for v in result["violations"] if v["violation_type"] == "circular_dependency"]
    assert len(cycle_viols) >= 1

    # Check health score calculation
    assert isinstance(result["health_score"], int)
    assert result["status"] == "Critical"

def test_pipeline_invalid_repo_path(sample_repo_paths):
    _, rules_path = sample_repo_paths
    pipeline = ArchitecturePipeline()
    result = pipeline.analyze("/invalid/non_existent_path_xyz", rules_path)

    assert result["status"] == "Error"
    assert "Invalid repository path" in result["error"]
    assert result["health_score"] == 0

def test_pipeline_invalid_rules_path(sample_repo_paths):
    repo_path, _ = sample_repo_paths
    pipeline = ArchitecturePipeline()
    result = pipeline.analyze(repo_path, "/invalid/missing_rules.yaml")

    assert result["status"] == "Error"
    assert "not found" in result["error"]
    assert result["health_score"] == 0

def test_pipeline_llm_fallback_resiliency(sample_repo_paths):
    repo_path, rules_path = sample_repo_paths
    # Ensure env variable is unset to test fallback path
    old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        pipeline = ArchitecturePipeline()
        result = pipeline.analyze(repo_path, rules_path)
        assert len(result["violations"]) > 0
        for v in result["violations"]:
            assert "LLM API key not found" in v["ai_explanation"] or "Failed to contact LLM" in v["ai_explanation"]
            assert "Manual code review" in v["ai_fix"] or "N/A" in v["ai_fix"]
    finally:
        if old_key:
            os.environ["ANTHROPIC_API_KEY"] = old_key
