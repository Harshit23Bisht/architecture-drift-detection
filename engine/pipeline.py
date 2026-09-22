import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from rules.schema import load_config, ArchitectureConfig
from parser.ast_walker import PythonAstWalker
from parser.resolver import DependencyResolver
from engine.graph_builder import GraphBuilder
from engine.rule_engine import RuleEngine
from engine.scorer import SeverityScorer
from engine.llm_explainer import LLMExplainer

logger = logging.getLogger("ArchitecturePipeline")

class ArchitecturePipeline:
    def __init__(self, explainer: Optional[LLMExplainer] = None):
        self.walker = PythonAstWalker()
        self.explainer = explainer or LLMExplainer()

    def analyze(self, repo_path: str, rules_path: str) -> Dict[str, Any]:
        """
        Executes the full 13-step architecture drift detection pipeline.
        """
        repo_dir = Path(repo_path).resolve()
        rules_file = Path(rules_path).resolve()

        # Step 1: Validate repository path
        if not repo_dir.exists() or not repo_dir.is_dir():
            return {
                "error": f"Invalid repository path: '{repo_path}' does not exist or is not a directory.",
                "status": "Error",
                "health_score": 0,
                "violations": [],
                "nodes": [],
                "links": []
            }

        # Step 2: Load and validate rules YAML config
        if not rules_file.exists() or not rules_file.is_file():
            return {
                "error": f"Rules configuration file not found: '{rules_path}'",
                "status": "Error",
                "health_score": 0,
                "violations": [],
                "nodes": [],
                "links": []
            }

        try:
            config: ArchitectureConfig = load_config(str(rules_file))
        except Exception as e:
            return {
                "error": f"Failed to load architecture rules YAML: {str(e)}",
                "status": "Error",
                "health_score": 0,
                "violations": [],
                "nodes": [],
                "links": []
            }

        # Step 3: Discover relevant source files (filtering out venv, git, caches)
        ignore_dirs = {".git", "venv", ".venv", "__pycache__", ".pytest_cache", "node_modules", "build", "dist"}
        python_files = []
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if file.endswith(".py"):
                    python_files.append(Path(root) / file)

        # Base package inference: use relative paths from repo_dir to align with import statements
        resolver = DependencyResolver(base_package=None)
        known_modules = set()
        file_module_map = {}

        for py_file in python_files:
            mod_name = resolver.resolve_module_name(str(py_file), str(repo_dir))
            known_modules.add(mod_name)
            file_module_map[str(py_file)] = mod_name


        # Step 4 & 5: Parse source files and extract AST elements
        parsed_files = []
        file_definitions = {}
        edge_metadata = {}

        for py_file in python_files:
            rel_file_path = str(py_file.relative_to(repo_dir))
            source_module = file_module_map[str(py_file)]

            try:
                with open(py_file, "rb") as f:
                    content = f.read()

                tree = self.walker.parse_file(content)
                imports = self.walker.extract_imports(tree.root_node)
                calls = self.walker.extract_calls(tree.root_node)
                defs = self.walker.extract_definitions(tree.root_node)

                file_definitions[rel_file_path] = defs
                parsed_files.append(rel_file_path)

                # Step 6: Resolve imports & dependencies
                resolver.add_edges_from_ast(source_module, imports, calls, known_modules=known_modules)

            except Exception as e:
                logger.warning(f"Failed to parse source file '{rel_file_path}': {e}")

        detailed_edges = resolver.get_detailed_edges()
        
        # Populate metadata for edge location lookup
        for e in detailed_edges:
            edge_metadata[(e["source"], e["target"])] = {"line": e.get("line"), "is_internal": e.get("is_internal")}

        # Step 7: Construct dependency graph (using internal edges primarily for rule checking)
        graph = GraphBuilder.build_from_edges(detailed_edges)

        # Step 8 & 9: Apply rules and detect violations
        rule_engine = RuleEngine(configured_layers=config.layers)
        raw_violations = rule_engine.detect_violations(graph, edge_metadata=edge_metadata)

        # Step 10 & 11: Calculate severity scoring and generate LLM/fallback explanations
        processed_violations = []
        violating_edges = set()

        for v in raw_violations:
            scored = SeverityScorer.score_violation(dict(v))
            explained = self.explainer.explain_violation(scored)
            processed_violations.append(explained)

            # Record violating edges for visual graph highlighting
            edge_or_cycle = v.get("edge_or_cycle", [])
            if len(edge_or_cycle) >= 2:
                for i in range(len(edge_or_cycle) - 1):
                    violating_edges.add((edge_or_cycle[i], edge_or_cycle[i+1]))

        # Calculate health score
        base_health = 100
        total_impact = sum(v.get("impact_score", 0) for v in processed_violations)
        final_health = max(0, base_health - total_impact)
        status_label = "Healthy" if final_health >= 70 else "Critical"

        # Construct visual nodes and links for frontend UI
        nodes = []
        layer_map = {}
        for idx, layer in enumerate(config.layers):
            layer_map[layer.name] = idx + 1

        for node_id in graph.nodes():
            layer_name = rule_engine._get_layer_for_module(node_id) or "Unmapped"
            group_id = layer_map.get(layer_name, 0)
            nodes.append({
                "id": node_id,
                "group": group_id,
                "layer": layer_name
            })

        links = []
        for src, tgt in graph.edges():
            is_viol = (src, tgt) in violating_edges
            line = edge_metadata.get((src, tgt), {}).get("line")
            links.append({
                "source": src,
                "target": tgt,
                "is_violation": is_viol,
                "line": line
            })

        return {
            "target_repository": str(repo_dir),
            "rules_path": str(rules_file),
            "discovered_files": parsed_files,
            "parsed_file_count": len(parsed_files),
            "total_dependencies": len(detailed_edges),
            "nodes": nodes,
            "links": links,
            "violations": processed_violations,
            "health_score": final_health,
            "status": status_label,
            "file_definitions": file_definitions,
            "summary": {
                "total_files": len(parsed_files),
                "total_edges": len(detailed_edges),
                "total_violations": len(processed_violations),
                "health_score": final_health
            }
        }
