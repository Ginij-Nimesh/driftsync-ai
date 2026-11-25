import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from github_retriever import fetch_pr_data, retrieve_relevant_sections
from llm_analyzer import analyze_drift
from database import init_db, save_scan, record_feedback, get_recent_scans_and_metrics

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

# Initialize SQLite relational tables on startup
init_db()

SAMPLE_PR = {
    "repo_full_name": "acme-org/cloud-cli",
    "pr_number": 412,
    "pr_title": "feat(cli): rename --env flag to --target and update default port to 8080",
    "diff": """diff --git a/src/cli.py b/src/cli.py
--- a/src/cli.py
+++ b/src/cli.py
@@ -12,8 +12,8 @@ def parse_args():
-    parser.add_argument("--env", default="dev", help="Deployment environment (dev, staging, prod)")
-    parser.add_argument("--port", type=int, default=3000, help="Local server port")
+    parser.add_argument("--target", default="development", help="Deployment target (development, staging, production)")
+    parser.add_argument("--port", type=int, default=8080, help="Local server port")
""",
    "docs": {
        "README.md": """# Cloud CLI

## Quickstart
Start the local development server using:
```bash
cloud-cli serve --env prod
```
By default, the server listens on port `3000`.

## Authentication
Run `cloud-cli login` to authenticate with your API token.
""",
        "docs/deployment.md": """# Deployment Guide

## Environments
Pass `--env staging` or `--env prod` when deploying to remote clusters.
"""
    }
}

@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "has_api_key": bool(os.getenv("GROQ_API_KEY"))})

@app.route("/api/history", methods=["GET"])
def history():
    try:
        limit = int(request.args.get("limit", 6))
        return jsonify(get_recent_scans_and_metrics(limit=limit))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/feedback", methods=["POST"])
def feedback():
    data = request.get_json() or {}
    issue_id = data.get("issue_id")
    rating = data.get("rating")
    if not issue_id or rating not in ("accurate", "false_positive"):
        return jsonify({"error": "Valid issue_id and rating ('accurate' or 'false_positive') are required."}), 400
    try:
        record_feedback(int(issue_id), rating)
        return jsonify({"status": "saved", **get_recent_scans_and_metrics()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json() or {}
    use_sample = data.get("use_sample", False)
    pr_url = (data.get("pr_url") or "").strip()

    try:
        if use_sample:
            pr_data = SAMPLE_PR
        else:
            if not pr_url:
                return jsonify({"error": "Please enter a valid GitHub Pull Request URL."}), 400
            pr_data = fetch_pr_data(pr_url)

        if not pr_data["docs"]:
            return jsonify({
                "repo": pr_data["repo_full_name"],
                "pr_number": pr_data["pr_number"],
                "pr_title": pr_data["pr_title"],
                "drift_detected": False,
                "summary": "No Markdown (.md) documentation files were found in this repository.",
                "issues": [],
                "retrieval_stats": {"total_chunks": 0, "retrieved_count": 0, "reduction_pct": 0}
            })

        retrieval = retrieve_relevant_sections(pr_data["diff"], pr_data["docs"], top_k=4)
        analysis = analyze_drift(
            pr_title=pr_data["pr_title"],
            diff_text=pr_data["diff"],
            selected_chunks=retrieval["selected_chunks"]
        )

        stats = {
            "total_chunks": retrieval["total_chunks"],
            "retrieved_count": retrieval["retrieved_count"],
            "reduction_pct": retrieval["reduction_pct"]
        }

        scan_id, saved_issues = save_scan(
            repo=pr_data["repo_full_name"],
            pr_number=pr_data["pr_number"],
            pr_title=pr_data["pr_title"],
            stats=stats,
            analysis=analysis
        )
        analysis["issues"] = saved_issues

        return jsonify({
            "scan_id": scan_id,
            "repo": pr_data["repo_full_name"],
            "pr_number": pr_data["pr_number"],
            "pr_title": pr_data["pr_title"],
            "retrieval_stats": stats,
            **analysis,
            **get_recent_scans_and_metrics()
        })

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
