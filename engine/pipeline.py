import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from rules.schema import load_config, ArchitectureConfig
from parser.factory import ParserFactory
from parser.resolver import DependencyResolver
from engine.graph_builder import GraphBuilder
from engine.rule_engine import RuleEngine
from engine.llm_explainer import LLMExplainer

try:
    from engine.learned_scorer import LearnedSeverityScorer
    _ml_scorer = LearnedSeverityScorer()
except Exception:
    _ml_scorer = None

try:
    from engine.scorer import SeverityScorer
except Exception:
    SeverityScorer = None

logger = logging.getLogger("ArchitecturePipeline")

class ArchitecturePipeline:
    def __init__(self, explainer: Optional[LLMExplainer] = None):
        self.explainer = explainer or LLMExplainer()
        self.learned_scorer = _ml_scorer

    def _default_heuristic_score(self, v_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Ensures forbidden layer violations score HIGH, circular dependencies score MEDIUM."""
        v_type = str(v_dict.get("violation_type", "")).lower()
        rule = str(v_dict.get("rule_broken", "")).lower()

        if "layer" in v_type or "forbidden" in v_type or "forbidden" in rule or "not allowed" in rule:
            v_dict["severity"] = "high"
            v_dict["impact_score"] = 50
        elif "circular" in v_type or "cycle" in v_type:
            v_dict["severity"] = "medium"
            v_dict["impact_score"] = 25
        else:
            v_dict["severity"] = "low"
            v_dict["impact_score"] = 10

        return v_dict

    def analyze(
        self,
        repo_path: str,
        rules_path: str,
        extra_ignore_dirs: Optional[List[str]] = None,
        use_ml_scoring: bool = True
    ) -> Dict[str, Any]:
        """
        Executes the full architecture drift detection pipeline across polyglot files
        with learned severity scoring and fallback support.
        """
        repo_dir = Path(repo_path).resolve()
        rules_file = Path(rules_path).resolve()

        if not repo_dir.exists() or not repo_dir.is_dir():
            return {
                "error": f"Invalid repository path: '{repo_path}' does not exist or is not a directory.",
                "status": "Error",
                "health_score": 0,
                "violations": [],
                "nodes": [],
                "links": []
            }

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

        ignore_dirs = {".git", "venv", ".venv", "__pycache__", ".pytest_cache", "node_modules", "build", "dist"}
        if config.ignore_dirs:
            ignore_dirs.update(config.ignore_dirs)
        if extra_ignore_dirs:
            ignore_dirs.update(extra_ignore_dirs)

        supported_extensions = {".py", ".js", ".jsx", ".ts", ".mjs"}
        source_files = []
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in supported_extensions:
                    source_files.append(file_path)

        resolver = DependencyResolver(base_package=None)
        known_modules = set()
        file_module_map = {}

        for src_file in source_files:
            mod_name = resolver.resolve_module_name(str(src_file), str(repo_dir))
            known_modules.add(mod_name)
            file_module_map[str(src_file)] = mod_name

        parsed_files = []
        file_definitions = {}
        edge_metadata = {}

        for src_file in source_files:
            rel_file_path = str(src_file.relative_to(repo_dir))
            source_module = file_module_map[str(src_file)]

            try:
                with open(src_file, "rb") as f:
                    content = f.read()

                walker = ParserFactory.get_walker(src_file)
                tree = walker.parse_file(content)
                root_node = getattr(tree, "root_node", tree)

                imports = walker.extract_imports(root_node)
                calls = walker.extract_calls(root_node)
                defs = getattr(walker, "extract_definitions", lambda node: [])(root_node)

                file_definitions[rel_file_path] = defs
                parsed_files.append(rel_file_path)
                resolver.add_edges_from_ast(source_module, imports, calls, known_modules=known_modules)

            except Exception as e:
                logger.warning(f"Failed to parse source file '{rel_file_path}': {e}")

        detailed_edges = resolver.get_detailed_edges()

        for e in detailed_edges:
            edge_metadata[(e["source"], e["target"])] = {"line": e.get("line"), "is_internal": e.get("is_internal")}

        graph = GraphBuilder.build_from_edges(detailed_edges)

        rule_engine = RuleEngine(configured_layers=config.layers)
        raw_violations = rule_engine.detect_violations(graph, edge_metadata=edge_metadata)

        processed_violations = []
        violating_edges = set()

        for v in raw_violations:
            violation_dict = dict(v)

            # Prioritize ML Scorer if enabled, then Heuristic Scorer, then default
            if use_ml_scoring and self.learned_scorer and hasattr(self.learned_scorer, "score_violation"):
                scored = self.learned_scorer.score_violation(violation_dict, graph)
            elif SeverityScorer:
                scored = SeverityScorer.score_violation(violation_dict)
            else:
                scored = self._default_heuristic_score(violation_dict)

            # Ensure forbidden calls are marked high
            rule_text = str(scored.get("rule_broken", "")).lower()
            if "forbidden" in rule_text or "not allowed" in rule_text:
                scored["severity"] = "high"
                if scored.get("impact_score", 0) < 50:
                    scored["impact_score"] = 50

            explained = self.explainer.explain_violation(scored)
            processed_violations.append(explained)

            edge_or_cycle = v.get("edge_or_cycle", [])
            if len(edge_or_cycle) >= 2:
                for i in range(len(edge_or_cycle) - 1):
                    violating_edges.add((edge_or_cycle[i], edge_or_cycle[i+1]))

        base_health = 100
        total_impact = sum(v.get("impact_score", 0) for v in processed_violations)
        final_health = max(0, base_health - total_impact)
        status_label = "Healthy" if final_health >= 70 else "Critical"

        nodes = []
        layer_map = {layer.name: idx + 1 for idx, layer in enumerate(config.layers)}

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
