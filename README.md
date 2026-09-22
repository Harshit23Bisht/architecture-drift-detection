# Architecture Drift Detection Tool

A production-ready tool designed to parse Python codebases using Tree-sitter AST queries, construct directed dependency graphs using NetworkX, evaluate layer and circular dependency rules defined in YAML, score violation severity, and provide AI explanations via Anthropic Claude (with automatic offline fallback).

---

## 🚀 Project Structure

```text
my_architecture_tool/
│
├── dashboard/                  # React 18 Frontend Dashboard (ForceGraph2D)
│   └── index.html              # Single-page interactive UI application
│
├── engine/                     # Central Core Engine & Orchestrator
│   ├── __init__.py
│   ├── graph_builder.py        # NetworkX directed graph builder
│   ├── llm_explainer.py        # Anthropic Claude API explainer with offline fallback
│   ├── pipeline.py             # ArchitecturePipeline central orchestrator
│   ├── rule_engine.py          # Layer violation & simple cycle detector
│   └── scorer.py               # Deterministic severity and impact scorer
│
├── parser/                     # Tree-sitter AST Parser & Resolver
│   ├── __init__.py
│   ├── ast_walker.py           # Tree-sitter Python AST query walker
│   └── resolver.py             # Dotted module path & relative import resolver
│
├── rules/                      # Rule Configuration Schemas
│   ├── __init__.py
│   └── schema.py               # Pydantic v2 YAML schema loader & validator
│
├── sample_repo/                # Sample repository with INJECTED violations
│   ├── architecture_rules.yaml # Sample rule configuration
│   └── myapp/                  # Source codebase with layer & cycle violations
│
├── sample_repo_valid/          # Sample repository with VALID architecture
│   ├── architecture_rules.yaml # Clean layering rules
│   └── myapp/                  # Valid source codebase (0 violations)
│
├── tests/                      # Automated Test Suite (38 Tests)
│   ├── test_api.py             # FastAPI REST endpoint integration tests
│   ├── test_engine.py          # Graph builder & rule engine unit tests
│   ├── test_hardening.py       # Engine hardening & error handling tests
│   ├── test_parser.py          # AST walker, resolver, & YAML schema tests
│   └── test_pipeline.py        # Pipeline integration & fallback tests
│
├── main.py                     # FastAPI REST API Backend Server
├── test_all.py                 # CLI Analysis Runner
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

---

## 🛠️ Prerequisites & Setup

Ensure you have **Python 3.10+** installed on your system.

### 1. Clone & Set Up Virtual Environment

**On Windows (PowerShell):**
```powershell
git clone https://github.com/Harshit23Bisht/architecture-drift-detection.git
cd architecture-drift-detection
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On macOS / Linux / Git Bash:**
```bash
git clone https://github.com/Harshit23Bisht/architecture-drift-detection.git
cd architecture-drift-detection
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🔑 Environment Variables

The tool operates fully out-of-the-box using built-in fallback explanations. To enable live Claude AI explanations, set the `ANTHROPIC_API_KEY` environment variable:

**PowerShell (Windows):**
```powershell
$env:ANTHROPIC_API_KEY="your_anthropic_api_key_here"
```

**Bash / macOS / Linux:**
```bash
export ANTHROPIC_API_KEY="your_anthropic_api_key_here"
```

---

## 📄 Example Architecture Rules (`architecture_rules.yaml`)

Define structural boundaries and allowed dependency flows between code layers:

```yaml
layers:
  - name: Controller
    allowed_calls:
      - Service
    forbidden_calls:
      - Repository
  - name: Service
    allowed_calls:
      - Repository
      - Service
  - name: Repository
    allowed_calls: []
```

---

## 💻 Running the Backend & Dashboard UI

### 1. Start FastAPI Backend API
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
The API server will run at `http://127.0.0.1:8000`.

### 2. Launch React Dashboard
Open `dashboard/index.html` directly in any web browser, or serve it via a local static server:
```bash
# Using Python built-in HTTP server
python -m http.server 3000 --directory dashboard
```
Then navigate to `http://localhost:3000` in your browser.

---

## ⚡ Running Analysis via CLI

Run a full end-to-end architecture scan from the command line:

```bash
python test_all.py
```

### Programmatic Python Usage

```python
from engine.pipeline import ArchitecturePipeline

pipeline = ArchitecturePipeline()
result = pipeline.analyze(
    repo_path="sample_repo",
    rules_path="sample_repo/architecture_rules.yaml"
)

print(f"Health Score: {result['health_score']}/100")
print(f"Status: {result['status']}")
print(f"Total Violations: {len(result['violations'])}")
```

---

## 🌐 Example API Requests

### Run Analysis (`POST /analyze`)

```bash
curl -X POST "http://127.0.0.1:8000/analyze" \
     -H "Content-Type: application/json" \
     -d '{
           "repo_path": "sample_repo",
           "rules_path": "sample_repo/architecture_rules.yaml"
         }'
```

### Fetch Graph Topology (`GET /graph`)
```bash
curl http://127.0.0.1:8000/graph
```

### Fetch Health Score (`GET /health-score`)
```bash
curl http://127.0.0.1:8000/health-score
```

---

## 🧪 Running Automated Tests

Run the complete test suite (38 unit, integration, and hardening tests):

```bash
pytest -v
```

---

## 📌 Features & Compliance Summary

- **AST Code Extraction:** Tree-sitter parsing for imports, aliased imports, relative imports, and call sites with 1-indexed line numbers.
- **Dependency Graph:** NetworkX directed graph representation distinguishing internal vs external dependencies.
- **Layer & Cycle Engine:** Exact package boundary layer matching, `forbidden_calls` enforcement, and simple cycle detection (`nx.simple_cycles`).
- **Severity & Explanations:** Deterministic severity impact scoring (85 for layer violations, 90/60 for cycles) with Claude 3 Haiku explanations and automatic offline fallback.
- **REST & Dashboard:** FastAPI REST API with Pydantic v2 schemas and React 2D force-directed graph UI.
