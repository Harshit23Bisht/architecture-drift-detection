import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from engine.pipeline import ArchitecturePipeline
from engine.llm_explainer import LLMExplainer
from engine.storage import HealthHistoryStorage

app = FastAPI(
    title="Architecture Drift API",
    description="Backend API for architecture drift detection and code parsing pipeline."
)

# Enable CORS for local frontend dashboard development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

explainer = LLMExplainer()
pipeline = ArchitecturePipeline(explainer=explainer)
storage = HealthHistoryStorage()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPO = os.path.join(BASE_DIR, "sample_repo")
DEFAULT_RULES = os.path.join(DEFAULT_REPO, "architecture_rules.yaml")

# --- PYDANTIC SCHEMAS ---

class AnalysisRequest(BaseModel):
    repo_path: Optional[str] = Field(default=None, description="Absolute or relative path to target repository")
    rules_path: Optional[str] = Field(default=None, description="Absolute or relative path to architecture YAML rules file")

class ViolationSchema(BaseModel):
    violation_id: Optional[str] = None
    rule_broken: str
    edge_or_cycle: List[str]
    source: Optional[str] = None
    target: Optional[str] = None
    source_layer: Optional[str] = None
    target_layer: Optional[str] = None
    line: Optional[int] = None
    violation_type: str
    severity: Optional[str] = None
    impact_score: Optional[int] = None
    ai_explanation: Optional[str] = None
    ai_fix: Optional[str] = None

class NodeSchema(BaseModel):
    id: str
    group: int
    layer: Optional[str] = None

class LinkSchema(BaseModel):
    source: str
    target: str
    is_violation: bool
    line: Optional[int] = None

class SummarySchema(BaseModel):
    total_files: int
    total_edges: int
    total_violations: int
    health_score: int

class AnalysisResponse(BaseModel):
    target_repository: Optional[str] = None
    rules_path: Optional[str] = None
    discovered_files: List[str] = Field(default_factory=list)
    parsed_file_count: int = 0
    total_dependencies: int = 0
    nodes: List[NodeSchema] = Field(default_factory=list)
    links: List[LinkSchema] = Field(default_factory=list)
    violations: List[ViolationSchema] = Field(default_factory=list)
    health_score: int = 100
    status: str = "Healthy"
    summary: Optional[SummarySchema] = None
    error: Optional[str] = None

class HealthHistoryItem(BaseModel):
    id: int
    repo_name: str
    commit_sha: str
    timestamp: str
    health_score: int
    total_violations: int
    high_count: int
    medium_count: int
    low_count: int
    parsed_file_count: int
    total_dependencies: int

# --- ENDPOINTS ---

@app.post("/analyze", response_model=AnalysisResponse)
def analyze(req: Optional[AnalysisRequest] = None):
    """
    Executes end-to-end architecture analysis on the specified target repository and records history.
    """
    repo = (req.repo_path if req and req.repo_path else DEFAULT_REPO)
    rules = (req.rules_path if req and req.rules_path else DEFAULT_RULES)

    repo_dir = Path(repo).resolve()
    rules_file = Path(rules).resolve()

    # Input validation
    if not repo_dir.exists() or not repo_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid repository path: '{repo}' does not exist or is not a directory."
        )

    if not rules_file.exists() or not rules_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rules file not found: '{rules}' does not exist or is not a valid file."
        )

    try:
        result = pipeline.analyze(str(repo_dir), str(rules_file))
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Save run to SQLite persistence storage automatically
        try:
            storage.save_run(result)
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal analysis pipeline failure: {str(e)}"
        )

@app.get("/health-history", response_model=List[HealthHistoryItem])
def get_health_history(limit: int = 50):
    """Returns historical architecture health scores across all repositories."""
    return storage.get_history(limit=limit)

@app.get("/health-history/{repo_name}", response_model=List[HealthHistoryItem])
def get_health_history_for_repo(repo_name: str, limit: int = 50):
    """Returns historical architecture health scores for a specific repository."""
    return storage.get_history(repo_name=repo_name, limit=limit)

@app.get("/graph")
def get_graph():
    """Returns the graph topology for visualization from active pipeline execution."""
    result = pipeline.analyze(DEFAULT_REPO, DEFAULT_RULES)
    return {"nodes": result.get("nodes", []), "links": result.get("links", [])}

@app.get("/violations")
def get_violations():
    """Returns architecture violations from active pipeline execution."""
    result = pipeline.analyze(DEFAULT_REPO, DEFAULT_RULES)
    return result.get("violations", [])

@app.get("/health-score")
def get_health_score():
    """Calculates overall health score from active pipeline execution."""
    result = pipeline.analyze(DEFAULT_REPO, DEFAULT_RULES)
    return {
        "health_score": result.get("health_score", 100),
        "status": result.get("status", "Healthy")
    }