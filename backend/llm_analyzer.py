import os
import json
import requests
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH)

GROQ_API_URL = "https://api." + "groq.com" + "/openai/v1/chat/completions"
MODEL_NAME = "openai/gpt-oss-20b"

def analyze_drift(pr_title: str, diff_text: str, selected_chunks: list):
    """
    Sends the PR code diff and retrieved Markdown sections to Groq Llama 3.1
    and enforces a strict structured JSON response.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Check your backend/.env file.")

    if not selected_chunks:
        return {
            "summary": "No Markdown documentation files were found in this repository to compare against the PR diff.",
            "drift_detected": False,
            "issues": []
        }

    docs_context = "\n\n---\n\n".join([
        f"FILE: {c['file_path']} (Section {c['section_index']})\n{c['text']}"
        for c in selected_chunks
    ])

    system_prompt = (
        "You are DriftSync AI, a senior developer documentation auditor. "
        "Compare the GitHub Pull Request code diff against the retrieved Markdown documentation sections. "
        "Identify ONLY real, factual documentation drift (e.g., renamed functions, changed CLI flags, updated parameters, "
        "removed features, or altered setup instructions that contradict the new code). "
        "You MUST respond strictly as a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "summary": "1-2 sentence executive summary of whether docs match the code changes",\n'
        '  "drift_detected": true or false,\n'
        '  "issues": [\n'
        "    {\n"
        '      "file_path": "exact markdown file path",\n'
        '      "severity": "HIGH" | "MEDIUM" | "LOW",\n'
        '      "outdated_text": "exact outdated sentence or snippet from the docs",\n'
        '      "suggested_fix": "updated replacement text that matches the new code",\n'
        '      "reason": "short explanation of what changed in the PR diff"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "If no documentation drift exists, set drift_detected to false and return an empty issues list []."
    )

    user_prompt = (
        f"PR TITLE: {pr_title}\n\n"
        f"=== CODE DIFF ===\n{diff_text[:7000]}\n\n"
        f"=== RETRIEVED DOCUMENTATION SECTIONS ===\n{docs_context}"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=25)
    if response.status_code != 200:
        raise RuntimeError(f"Groq API error ({response.status_code}): {response.text}")

    raw_content = response.json()["choices"][0]["message"]["content"]
    return json.loads(raw_content)
