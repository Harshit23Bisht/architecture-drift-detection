import os
import json
from pathlib import Path
from engine.pipeline import ArchitecturePipeline

def run_cli_analysis():
    base_dir = Path(__file__).parent.resolve()
    sample_repo = base_dir / "sample_repo"
    sample_rules = sample_repo / "architecture_rules.yaml"

    print("\n" + "="*60)
    print("ARCHITECTURE DRIFT DETECTION - UNIFIED PIPELINE RUNNER")
    print("="*60)

    if not sample_repo.exists() or not sample_rules.exists():
        print(f"[ERROR] Sample repo or rules file missing at {sample_repo}")
        return

    print(f"\nScanning Repository: {sample_repo}")
    print(f"Using Rules File:     {sample_rules}\n")

    pipeline = ArchitecturePipeline()
    result = pipeline.analyze(str(sample_repo), str(sample_rules))

    if result.get("error"):
        print(f"[ERROR] Pipeline execution failed: {result['error']}")
        return

    print("--- SCAN SUMMARY ---")
    print(f"Target Repository:  {result['target_repository']}")
    print(f"Discovered Files:   {result['parsed_file_count']}")
    print(f"Dependency Edges:   {result['total_dependencies']}")
    print(f"Health Score:       {result['health_score']}/100 ({result['status']})")
    print(f"Total Violations:   {len(result['violations'])}\n")

    print("--- DISCOVERED FILES ---")
    for file in result['discovered_files']:
        print(f"  - {file}")

    print("\n--- DEPENDENCY EDGES ---")
    for link in result['links']:
        viol_tag = "[VIOLATION]" if link['is_violation'] else "[OK]"
        line_info = f"(Line {link['line']})" if link.get('line') else ""
        print(f"  {viol_tag} {link['source']} -> {link['target']} {line_info}")

    print("\n--- DETECTED VIOLATIONS ---")
    for idx, v in enumerate(result['violations'], 1):
        print(f"\n[{idx}] {v.get('violation_id', 'V-?')} - Type: {v.get('violation_type').upper()}")
        print(f"    Rule Broken: {v.get('rule_broken')}")
        print(f"    Involved:    {v.get('edge_or_cycle')}")
        print(f"    Severity:    {v.get('severity', 'N/A').upper()} (Impact Score: {v.get('impact_score')})")
        print(f"    Why:         {v.get('ai_explanation')}")
        print(f"    Fix:         {v.get('ai_fix')}")

    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    run_cli_analysis()
