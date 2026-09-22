import sys
import argparse
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List

from rules.schema import load_config
from engine.pipeline import ArchitecturePipeline
from engine.storage import HealthHistoryStorage

SEVERITY_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}

def evaluate_threshold(violations: List[Dict[str, Any]], fail_on_threshold: str) -> bool:
    """
    Returns True if any violation meets or exceeds the fail_on severity threshold.
    Threshold ordering: LOW (1) <= MEDIUM (2) <= HIGH (3).
    """
    fail_on_level = SEVERITY_ORDER.get(fail_on_threshold.upper(), 3)

    for v in violations:
        v_sev = v.get("severity", "LOW").upper()
        v_level = SEVERITY_ORDER.get(v_sev, 1)
        if v_level >= fail_on_level:
            return True

    return False

def detect_git_changed_files(repo_path: str) -> List[str]:
    """Detects staged or modified Python files in git repository context."""
    try:
        cmd = ["git", "diff", "--cached", "--name-only", "*.py"]
        output = subprocess.check_output(cmd, cwd=repo_path, stderr=subprocess.DEVNULL).decode("utf-8")
        files = [f.strip() for f in output.splitlines() if f.strip()]
        if not files:
            cmd = ["git", "diff", "--name-only", "HEAD", "*.py"]
            output = subprocess.check_output(cmd, cwd=repo_path, stderr=subprocess.DEVNULL).decode("utf-8")
            files = [f.strip() for f in output.splitlines() if f.strip()]
        return files
    except Exception:
        return []

def run_scan(args) -> int:
    repo_path = Path(args.repo).resolve()
    rules_path = Path(args.rules).resolve()

    if not repo_path.exists() or not repo_path.is_dir():
        print(f"[ERROR] Target repository path '{repo_path}' does not exist or is not a directory.")
        return 1

    if not rules_path.exists() or not rules_path.is_file():
        print(f"[ERROR] Architecture rules file '{rules_path}' not found.")
        return 1

    # Determine fail_on threshold from CLI args or YAML rule configuration
    fail_on = args.fail_on
    if not fail_on:
        try:
            config = load_config(str(rules_path))
            fail_on = config.ci.fail_on if config.ci else "HIGH"
        except Exception:
            fail_on = "HIGH"

    fail_on = fail_on.upper()

    print("\n" + "=" * 60)
    print("ARCHITECTURE DRIFT DETECTION - CLI ANALYSIS SCAN")
    print("=" * 60)
    print(f"Target Repository:  {repo_path}")
    print(f"Rules File:         {rules_path}")
    print(f"Severity Threshold: FAIL ON {fail_on}")

    # Detect git changed files for context logging
    changed_files = detect_git_changed_files(str(repo_path))
    if changed_files:
        print(f"Git Changed Files:  {len(changed_files)} file(s) modified")
        for cf in changed_files[:5]:
            print(f"  - {cf}")
        if len(changed_files) > 5:
            print(f"  ... and {len(changed_files) - 5} more")

    print("\nRunning full architecture dependency analysis...")

    pipeline = ArchitecturePipeline()
    result = pipeline.analyze(str(repo_path), str(rules_path), extra_ignore_dirs=getattr(args, "ignore", None))

    if result.get("error"):
        print(f"\n[ERROR] Analysis failed: {result['error']}")
        return 1

    violations = result.get("violations", [])
    high_count = sum(1 for v in violations if v.get("severity", "").upper() == "HIGH")
    med_count = sum(1 for v in violations if v.get("severity", "").upper() == "MEDIUM")
    low_count = sum(1 for v in violations if v.get("severity", "").upper() == "LOW")

    print("\n--- ANALYSIS RESULTS ---")
    print(f"Files Analyzed:     {result.get('parsed_file_count', 0)}")
    print(f"Dependencies:       {result.get('total_dependencies', 0)}")
    print(f"Health Score:       {result.get('health_score', 100)}/100 ({result.get('status', 'Healthy')})")
    print(f"Total Violations:   {len(violations)} (HIGH: {high_count}, MEDIUM: {med_count}, LOW: {low_count})")

    if violations:
        print("\n--- DETECTED VIOLATIONS ---")
        for idx, v in enumerate(violations, 1):
            sev = v.get("severity", "LOW").upper()
            line_str = f" Line {v['line']}" if v.get("line") else ""
            print(f"[{idx}] {v.get('violation_id', 'V-?')} [{sev}] {v.get('rule_broken')}{line_str}")
            print(f"    Involved: {v.get('edge_or_cycle')}")
            print(f"    Fix:      {v.get('ai_fix')}")

    # Save to SQLite persistence if requested
    if args.save_history:
        try:
            storage = HealthHistoryStorage()
            run_id = storage.save_run(result)
            print(f"\n[PERSISTENCE] Health score recorded in history (Run ID: {run_id})")
        except Exception as e:
            print(f"\n[WARNING] Failed to record health history: {e}")

    # Evaluate severity threshold for exit code
    threshold_breached = evaluate_threshold(violations, fail_on)

    if threshold_breached:
        print(f"\n[FAIL] Architecture check failed: Detected violations meeting or exceeding threshold '{fail_on}'.")
        print("=" * 60 + "\n")
        return 1
    else:
        print(f"\n[SUCCESS] Architecture check passed! No violations meeting threshold '{fail_on}'.")
        print("=" * 60 + "\n")
        return 0

def install_hook(args) -> int:
    repo_path = Path(args.repo).resolve()
    git_dir = repo_path / ".git"

    if not git_dir.exists() or not git_dir.is_dir():
        print(f"[ERROR] '{repo_path}' is not a valid Git repository root (missing .git directory).")
        return 1

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_type = args.hook_type.lower()
    hook_file = hooks_dir / hook_type

    python_executable = sys.executable

    hook_script = f"""#!/bin/sh
# Architecture Drift Detection Git {hook_type} hook
echo "Running Architecture Drift Detection check..."
"{python_executable}" -m engine.cli scan --repo . --rules architecture_rules.yaml --fail-on {args.fail_on}
RESULT=$?
if [ $RESULT -ne 0 ]; then
    echo "Architecture check failed! Commit/push aborted."
    exit 1
fi
exit 0
"""

    try:
        with open(hook_file, "w", encoding="utf-8") as f:
            f.write(hook_script)

        # Make executable on Unix/Linux/macOS
        try:
            os.chmod(hook_file, 0o755)
        except Exception:
            pass

        print(f"[SUCCESS] Git {hook_type} hook installed at '{hook_file}'.")
        return 0
    except Exception as e:
        print(f"[ERROR] Failed to install Git hook: {e}")
        return 1

def main():
    parser = argparse.ArgumentParser(description="Architecture Drift Detection CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Command: scan
    scan_parser = subparsers.add_parser("scan", help="Run architecture scan on repository")
    scan_parser.add_argument("--repo", default=".", help="Target repository directory (default: .)")
    scan_parser.add_argument("--rules", default="architecture_rules.yaml", help="Path to rules YAML file (default: architecture_rules.yaml)")
    scan_parser.add_argument("--fail-on", choices=["HIGH", "MEDIUM", "LOW", "high", "medium", "low"], default=None, help="Severity threshold to fail scan")
    scan_parser.add_argument("--ignore", nargs="*", default=None, help="Additional directory names to ignore during scan")
    scan_parser.add_argument("--no-history", dest="save_history", action="store_false", help="Disable recording to SQLite health history")
    scan_parser.set_defaults(save_history=True)

    # Command: install-hook
    hook_parser = subparsers.add_parser("install-hook", help="Install local Git pre-commit or pre-push hook")
    hook_parser.add_argument("--repo", default=".", help="Target repository directory")
    hook_parser.add_argument("--hook-type", choices=["pre-commit", "pre-push"], default="pre-commit", help="Git hook type")
    hook_parser.add_argument("--fail-on", default="HIGH", help="Severity threshold for hook execution")

    args = parser.parse_args()

    if args.command == "scan":
        sys.exit(run_scan(args))
    elif args.command == "install-hook":
        sys.exit(install_hook(args))
    else:
        # Default behavior: run scan on current directory
        args.repo = "."
        args.rules = "architecture_rules.yaml" if Path("architecture_rules.yaml").exists() else "sample_repo/architecture_rules.yaml"
        args.fail_on = None
        args.ignore = None
        args.save_history = True
        sys.exit(run_scan(args))

if __name__ == "__main__":
    main()
