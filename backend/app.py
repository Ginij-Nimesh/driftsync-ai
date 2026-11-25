import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from github_retriever import fetch_pr_data, retrieve_relevant_sections
from llm_analyzer import analyze_drift

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

SAMPLE_PR = {
    "repo_full_name": "acme-cloud/cli-deploy",
    "pr_number": 142,
    "pr_title": "feat!: rename --env flag to --target and change default port to 8080",
    "diff": """diff --git a/cli.py b/cli.py
--- a/cli.py
+++ b/cli.py
@@ -12,10 +12,10 @@ def parse_args():
     parser = argparse.ArgumentParser(description="Deploy service to cloud")
-    parser.add_argument("--env", choices=["dev", "staging", "prod"], default="dev", help="Deployment environment")
-    parser.add_argument("--port", type=int, default=3000, help="Server port")
+    parser.add_argument("--target", choices=["local", "staging", "production"], default="local", help="Deployment target")
+    parser.add_argument("--port", type=int, default=8080, help="Server port")
     return parser.parse_args()
""",
    "docs": {
        "README.md": """# Acme Cloud CLI

Quickly deploy microservices from your terminal.

## Quick Start

Run the deployment command specifying your environment:

```bash
acme-deploy --env prod --port 3000
```

By default, the local server starts on port `3000` and uses the `dev` environment. Valid environments are `dev`, `staging`, and `prod`.

## Authentication

Set `ACME_TOKEN` in your terminal before deploying.
""",
        "CONTRIBUTING.md": """# Contributing

1. Fork the repository.
2. Run `pytest` before opening a Pull Request.
"""
    }
}

@app.route("/")
def serve_index():
    return app.send_static_file("index.html")

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "service": "DriftSync AI Backend"})

@app.route("/api/analyze", methods=["POST"])
def analyze_pr():
    data = request.get_json(silent=True) or {}
    use_sample = data.get("use_sample", False)
    pr_url = data.get("pr_url", "").strip()

    try:
        if use_sample:
            pr_data = SAMPLE_PR
        else:
            if not pr_url:
                return jsonify({"error": "Please enter a valid GitHub Pull Request URL."}), 400
            pr_data = fetch_pr_data(pr_url)

        retrieval = retrieve_relevant_sections(pr_data["diff"], pr_data["docs"], top_k=4)
        analysis = analyze_drift(
            pr_title=pr_data["pr_title"],
            diff_text=pr_data["diff"],
            selected_chunks=retrieval["selected_chunks"]
        )

        return jsonify({
            "repo": pr_data["repo_full_name"],
            "pr_number": pr_data["pr_number"],
            "pr_title": pr_data["pr_title"],
            "retrieval_stats": {
                "total_chunks": retrieval["total_chunks"],
                "retrieved_count": retrieval["retrieved_count"],
                "reduction_pct": retrieval["reduction_pct"]
            },
            "analysis": analysis
        })

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
