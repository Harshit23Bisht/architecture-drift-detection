from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from engine.scorer import SeverityScorer
from engine.llm_explainer import LLMExplainer

app = FastAPI(title="Architecture Drift API")

# Allow local frontend to access the API without CORS issues
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

explainer = LLMExplainer()

# Mocking a processed graph state representing an injected violation
MOCK_NODES = [
    {"id": "myapp.controllers.auth", "group": 1},
    {"id": "myapp.services.auth", "group": 2},
    {"id": "myapp.repository.user", "group": 3}
]

MOCK_LINKS = [
    {"source": "myapp.controllers.auth", "target": "myapp.services.auth", "is_violation": False},
    {"source": "myapp.controllers.auth", "target": "myapp.repository.user", "is_violation": True}
]

RAW_VIOLATIONS = [
    {
        "rule_broken": "Layer 'Controller' is not allowed to call 'Repository'",
        "edge_or_cycle": ["myapp.controllers.auth", "myapp.repository.user"],
        "violation_type": "layer_violation"
    }
]

@app.get("/graph")
def get_graph():
    """Returns the graph topology for visualization."""
    return {"nodes": MOCK_NODES, "links": MOCK_LINKS}

@app.get("/violations")
def get_violations():
    """Processes, scores, explains, and returns architecture violations."""
    processed_violations = []
    for v in RAW_VIOLATIONS:
        scored = SeverityScorer.score_violation(dict(v))
        explained = explainer.explain_violation(scored)
        processed_violations.append(explained)
    return processed_violations

@app.get("/health-score")
def get_health_score():
    """Calculates the overall architecture health score."""
    base_score = 100
    for v in RAW_VIOLATIONS:
        scored = SeverityScorer.score_violation(dict(v))
        base_score -= scored.get("impact_score", 0)
    
    final_score = max(0, base_score)
    return {"health_score": final_score, "status": "Healthy" if final_score > 70 else "Critical"}