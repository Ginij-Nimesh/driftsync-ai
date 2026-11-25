import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "driftsync.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates relational tables for scan history and LLM evaluation feedback."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                pr_title TEXT NOT NULL,
                summary TEXT NOT NULL,
                drift_detected INTEGER NOT NULL,
                total_chunks INTEGER NOT NULL,
                retrieved_count INTEGER NOT NULL,
                reduction_pct INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drift_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                severity TEXT NOT NULL,
                outdated_text TEXT NOT NULL,
                suggested_fix TEXT NOT NULL,
                reason TEXT NOT NULL,
                feedback TEXT DEFAULT NULL,
                FOREIGN KEY (scan_id) REFERENCES scans(id)
            )
        """)
        conn.commit()

def save_scan(repo: str, pr_number: int, pr_title: str, stats: dict, analysis: dict):
    """Persists a completed PR audit and its individual drift issues, returning IDs."""
    created_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO scans (repo, pr_number, pr_title, summary, drift_detected, total_chunks, retrieved_count, reduction_pct, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repo,
                pr_number,
                pr_title,
                analysis.get("summary", ""),
                1 if analysis.get("drift_detected") else 0,
                stats.get("total_chunks", 0),
                stats.get("retrieved_count", 0),
                stats.get("reduction_pct", 0),
                created_at
            )
        )
        scan_id = cursor.lastrowid
        saved_issues = []
        for issue in analysis.get("issues", []):
            issue_cursor = conn.execute(
                """
                INSERT INTO drift_issues (scan_id, file_path, severity, outdated_text, suggested_fix, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_id,
                    issue.get("file_path", ""),
                    issue.get("severity", "MEDIUM"),
                    issue.get("outdated_text", ""),
                    issue.get("suggested_fix", ""),
                    issue.get("reason", "")
                )
            )
            issue_with_id = dict(issue)
            issue_with_id["id"] = issue_cursor.lastrowid
            issue_with_id["feedback"] = None
            saved_issues.append(issue_with_id)
        conn.commit()
    return scan_id, saved_issues

def record_feedback(issue_id: int, rating: str):
    """Records human-in-the-loop LLM accuracy feedback ('accurate' or 'false_positive')."""
    if rating not in ("accurate", "false_positive"):
        raise ValueError("Invalid rating value.")
    with get_connection() as conn:
        conn.execute(
            "UPDATE drift_issues SET feedback = ? WHERE id = ?",
            (rating, issue_id)
        )
        conn.commit()

def get_recent_scans_and_metrics(limit: int = 6):
    """Fetches recent scan history and live LLM precision evaluation metrics."""
    with get_connection() as conn:
        scans = [
            dict(row) for row in conn.execute(
                "SELECT * FROM scans ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        ]
        eval_row = conn.execute("""
            SELECT
                COUNT(feedback) AS total_rated,
                SUM(CASE WHEN feedback = 'accurate' THEN 1 ELSE 0 END) AS accurate_count
            FROM drift_issues
            WHERE feedback IS NOT NULL
        """).fetchone()

    total_rated = eval_row["total_rated"] or 0
    accurate_count = eval_row["accurate_count"] or 0
    precision_pct = round((accurate_count / total_rated) * 100) if total_rated > 0 else None

    return {
        "recent_scans": scans,
        "eval_metrics": {
            "total_rated": total_rated,
            "accurate_count": accurate_count,
            "precision_pct": precision_pct
        }
    }
