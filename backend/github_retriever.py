import re
import requests

GITHUB_API = "https://api." + "github.com"
GITHUB_RAW = "https://raw." + "githubusercontent.com"

def parse_pr_url(pr_url: str):
    """Extracts owner, repo, and PR number from a GitHub PR URL."""
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url.strip())
    if not match:
        raise ValueError("Invalid GitHub PR URL. Expected format: https://github.com")
    return match.group(1), match.group(2), int(match.group(3))

def fetch_pr_data(pr_url: str):
    """Fetches PR metadata, code diff, and Markdown files from GitHub."""
    owner, repo, pr_number = parse_pr_url(pr_url)
    headers = {"Accept": "application/vnd.github.v3+json"}

    # 1. Fetch PR metadata (to get head branch ref & PR title)
    pr_api = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    pr_res = requests.get(pr_api, headers=headers, timeout=15)
    if pr_res.status_code != 200:
        raise RuntimeError(f"GitHub API error ({pr_res.status_code}): Could not fetch PR details.")
    pr_info = pr_res.json()
    pr_title = pr_info.get("title", f"PR #{pr_number}")
    head_sha = pr_info["head"]["sha"]

    # 2. Fetch raw unified diff of the PR
    diff_headers = {"Accept": "application/vnd.github.v3.diff"}
    diff_res = requests.get(pr_api, headers=diff_headers, timeout=15)
    diff_text = diff_res.text if diff_res.status_code == 200 else ""

    # 3. Fetch repository file tree to locate .md documentation files
    tree_api = f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{head_sha}?recursive=1"
    tree_res = requests.get(tree_api, headers=headers, timeout=15)
    md_files = []
    if tree_res.status_code == 200:
        for item in tree_res.json().get("tree", []):
            path = item.get("path", "")
            if item.get("type") == "blob" and path.lower().endswith(".md"):
                md_files.append(path)

    # Prioritize README.md and limit to top 5 Markdown files
    md_files.sort(key=lambda p: (0 if "readme" in p.lower() else 1, len(p)))
    docs = {}
    for md_path in md_files[:5]:
        raw_url = f"{GITHUB_RAW}/{owner}/{repo}/{head_sha}/{md_path}"
        raw_res = requests.get(raw_url, timeout=10)
        if raw_res.status_code == 200:
            docs[md_path] = raw_res.text

    return {
        "repo_full_name": f"{owner}/{repo}",
        "pr_number": pr_number,
        "pr_title": pr_title,
        "diff": diff_text[:12000],
        "docs": docs
    }

def extract_code_symbols(diff_text: str):
    """Extracts changed identifiers, function names, and CLI flags from added/removed lines."""
    changed_lines = [
        line[1:] for line in diff_text.splitlines()
        if (line.startswith("+") or line.startswith("-"))
        and not line.startswith("+++") and not line.startswith("---")
    ]
    joined = "\n".join(changed_lines)
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_-]{2,}", joined))
    stopwords = {"def", "return", "import", "from", "class", "const", "let", "var", "true", "false", "none", "self"}
    return {t.lower() for t in tokens if t.lower() not in stopwords}

def retrieve_relevant_sections(diff_text: str, docs: dict, top_k: int = 4):
    """
    Two-stage retrieval: splits Markdown files into sections and ranks them
    by overlap with changed code symbols from the PR diff.
    """
    symbols = extract_code_symbols(diff_text)
    all_chunks = []

    for file_path, content in docs.items():
        raw_sections = re.split(r"\n(?=#{1,3}\s)|\n\n+", content)
        for idx, sec in enumerate(raw_sections):
            cleaned = sec.strip()
            if len(cleaned) < 25:
                continue
            words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_-]{2,}", cleaned.lower()))
            overlap = len(symbols.intersection(words))
            score = overlap + (0.5 if "readme" in file_path.lower() and idx < 3 else 0.0)
            all_chunks.append({
                "file_path": file_path,
                "section_index": idx + 1,
                "text": cleaned[:1500],
                "score": score
            })

    total_chunks = len(all_chunks)
    all_chunks.sort(key=lambda c: c["score"], reverse=True)
    selected = all_chunks[:top_k]

    reduction_pct = round(((total_chunks - len(selected)) / total_chunks) * 100) if total_chunks > len(selected) else 0

    return {
        "selected_chunks": selected,
        "total_chunks": total_chunks,
        "retrieved_count": len(selected),
        "reduction_pct": reduction_pct
    }
