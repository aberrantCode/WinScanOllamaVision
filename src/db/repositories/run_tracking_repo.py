"""Run tracking repository for managing analysis run statistics."""

from typing import Any

from db.connection import DatabaseConnection


class RunTrackingRepository:
    """Manages analysis run tracking and error logging."""

    def __init__(self, conn: DatabaseConnection):
        """Initialize run tracking repository."""
        self.conn = conn

    def start_run(self, run_id: str, total_files: int) -> None:
        """Start tracking a new analysis run."""
        self.conn.execute(
            "INSERT INTO analysis_runs (run_id, total_files, status) VALUES (?, ?, 'running')",
            (run_id, total_files),
        )
        self.conn.commit()

    def update_run(
        self,
        run_id: str,
        analyzed: int = 0,
        cached: int = 0,
        errors: int = 0,
        skipped: int = 0,
        status: str = "running",
    ) -> None:
        """Update analysis run statistics."""
        if status in ("completed", "failed"):
            query = "UPDATE analysis_runs SET analyzed = ?, cached = ?, errors = ?, skipped = ?, status = ?, completed_at = CURRENT_TIMESTAMP, duration_ms = CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400000 AS INTEGER) WHERE run_id = ?"
        else:
            query = "UPDATE analysis_runs SET analyzed = ?, cached = ?, errors = ?, skipped = ?, status = ? WHERE run_id = ?"

        params = (
            (analyzed, cached, errors, skipped, status, run_id)
            if status in ("completed", "failed")
            else (analyzed, cached, errors, skipped, status, run_id)
        )
        self.conn.execute(query, params)
        self.conn.commit()

    def save_error(
        self, run_id: str, file_path: str, error_message: str, error_type: str = "analysis_failed"
    ) -> None:
        """Save an analysis error record."""
        self.conn.execute(
            "INSERT INTO analysis_errors (run_id, file_path, error_message, error_type) VALUES (?, ?, ?, ?)",
            (run_id, file_path, error_message, error_type),
        )
        self.conn.commit()

    def get_recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent analysis runs with aggregated statistics."""
        runs = self.conn.fetch_all_dicts(
            "SELECT run_id, total_files, analyzed, cached, errors, skipped, started_at as timestamp, completed_at, duration_ms, status FROM analysis_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )

        for run in runs:
            run["duration_seconds"] = (run["duration_ms"] // 1000) if run["duration_ms"] else 0
            del run["duration_ms"]

            if run["status"] == "running":
                run["status"] = "running"
            elif run["errors"] == 0:
                run["status"] = "success"
            elif run["errors"] == run["total_files"]:
                run["status"] = "failed"
            else:
                run["status"] = "partial"

        return runs
