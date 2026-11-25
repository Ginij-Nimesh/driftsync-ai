# DriftSync AI — Automated GitHub PR Documentation Drift Detector

**Live Demo:** [https://driftsync-ai.onrender.com](https://driftsync-ai.onrender.com) *(Note: Hosted on Render free tier—may take ~30–50s to wake up on first request.)*

**DriftSync AI** audits public GitHub Pull Requests against repository Markdown documentation to catch outdated CLI flags, renamed functions, and changed default values before code merges.


## Key Engineering Highlights
- **Two-Stage Hybrid Retrieval (`backend/github_retriever.py`):** Extracts changed code symbols from unified PR diffs and ranks Markdown documentation chunks by lexical overlap—reducing LLM context size by up to **97%** on large repositories.
- **Structured JSON Auditing (`backend/llm_analyzer.py`):** Enforces strict JSON schema outputs via Groq (`openai/gpt-oss-20b` at `temperature=0.1`) to prevent hallucinated fixes and return severity-ranked diffs (`HIGH`, `MEDIUM`, `LOW`).
- **Relational Persistence & LLM Eval Loop (`backend/database.py`):** Stores scan history and drift findings in **SQLite** (`scans` and `drift_issues` tables) with interactive **Accurate / False Positive** human-in-the-loop precision tracking.


## Project Structure
```text
driftsync-ai/
├── backend/
│   ├── app.py               # Flask REST API & static frontend server
│   ├── github_retriever.py  # GitHub PR diff fetcher & Markdown chunk ranker
│   ├── llm_analyzer.py      # Groq structured JSON drift detector
│   ├── database.py          # SQLite schema, scan logging & eval metrics
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Environment variable template
└── frontend/
    ├── index.html           # Single-page dashboard UI
    ├── style.css            # Dark-mode responsive diff & history styling
    └── app.js               # Async API client, clipboard actions & eval handlers
```


## Quick Local Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/Ginij-Nimesh/driftsync-ai
   cd driftsync-ai
   ```
2. **Create a virtual environment & install dependencies:**
   ```bash
   python -m venv venv
   # Windows: .\venv\Scripts\activate (or .\venv\bin\Activate.ps1)  |  Mac/Linux: source venv/bin/activate
   pip install -r backend/requirements.txt
   ```
3. **Configure your API key:**
   Copy `backend/.env.example` to `backend/.env` and add your free Groq API key:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```
4. **Run the application:**
   ```bash
   python backend/app.py
   ```
   Open `http://127.0.0.1:5000` in your browser and click **Try Sample PR** or test a live PR such as `https://github.com/Ginij-Nimesh/drift-demo-target/pull/1`.
