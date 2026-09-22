import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

class HealthHistoryStorage:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = Path(__file__).parent.parent.resolve()
            db_path = str(base_dir / "architecture_history.db")

        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creates the sqlite table if it does not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS health_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_name TEXT NOT NULL,
                    commit_sha TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    health_score INTEGER NOT NULL,
                    total_violations INTEGER NOT NULL,
                    high_count INTEGER NOT NULL,
                    medium_count INTEGER NOT NULL,
                    low_count INTEGER NOT NULL,
                    parsed_file_count INTEGER NOT NULL,
                    total_dependencies INTEGER NOT NULL
                )
            """)
            conn.commit()

    def _get_current_git_sha(self, repo_dir: Optional[str] = None) -> str:
        """Helper to get current git commit SHA if available."""
        try:
            cwd = repo_dir if (repo_dir and os.path.exists(repo_dir)) else None
            out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, stderr=subprocess.DEVNULL)
            return out.decode("utf-8").strip()[:8]
        except Exception:
            return "local"

    def save_run(self, result_dict: Dict[str, Any], commit_sha: Optional[str] = None, repo_name: Optional[str] = None) -> int:
        """
        Saves an analysis result payload to the SQLite history table.
        """
        target_repo = result_dict.get("target_repository", "")
        if not repo_name:
            repo_name = Path(target_repo).name if target_repo else "unknown"

        if not commit_sha:
            commit_sha = self._get_current_git_sha(target_repo)

        violations = result_dict.get("violations", [])
        high_count = sum(1 for v in violations if v.get("severity", "").upper() == "HIGH")
        medium_count = sum(1 for v in violations if v.get("severity", "").upper() == "MEDIUM")
        low_count = sum(1 for v in violations if v.get("severity", "").upper() == "LOW")

        timestamp = datetime.utcnow().isoformat() + "Z"
        health_score = result_dict.get("health_score", 100)
        total_violations = len(violations)
        parsed_file_count = result_dict.get("parsed_file_count", 0)
        total_dependencies = result_dict.get("total_dependencies", 0)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO health_history (
                    repo_name, commit_sha, timestamp, health_score,
                    total_violations, high_count, medium_count, low_count,
                    parsed_file_count, total_dependencies
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                repo_name, commit_sha, timestamp, health_score,
                total_violations, high_count, medium_count, low_count,
                parsed_file_count, total_dependencies
            ))
            conn.commit()
            return cursor.lastrowid

    def get_history(self, repo_name: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves historical health runs, optionally filtered by repository name.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if repo_name:
                cursor.execute("""
                    SELECT * FROM health_history
                    WHERE repo_name = ? OR repo_name LIKE ?
                    ORDER BY id DESC LIMIT ?
                """, (repo_name, f"%{repo_name}%", limit))
            else:
                cursor.execute("""
                    SELECT * FROM health_history
                    ORDER BY id DESC LIMIT ?
                """, (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def clear_history(self, repo_name: Optional[str] = None):
        """Clears records from the database for testing purposes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if repo_name:
                cursor.execute("DELETE FROM health_history WHERE repo_name = ?", (repo_name,))
            else:
                cursor.execute("DELETE FROM health_history")
            conn.commit()
