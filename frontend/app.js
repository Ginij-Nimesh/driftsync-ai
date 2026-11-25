const prUrlInput = document.getElementById("prUrl");
const analyzeBtn = document.getElementById("analyzeBtn");
const sampleBtn = document.getElementById("sampleBtn");
const loader = document.getElementById("loader");
const errorBox = document.getElementById("errorBox");
const results = document.getElementById("results");

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderHistory(recentScans, evalMetrics) {
  const section = document.getElementById("historySection");
  const list = document.getElementById("historyList");
  const badge = document.getElementById("evalBadge");

  if (evalMetrics && evalMetrics.total_rated > 0) {
    badge.textContent = `LLM Precision: ${evalMetrics.precision_pct}% (${evalMetrics.accurate_count}/${evalMetrics.total_rated} rated)`;
  } else {
    badge.textContent = "LLM Precision: No ratings yet";
  }

  if (!recentScans || recentScans.length === 0) {
    section.style.display = "none";
    return;
  }

  section.style.display = "block";
  list.innerHTML = recentScans.map(scan => `
    <div class="history-item">
      <div>
        <strong>${escapeHtml(scan.repo)}</strong> &mdash; PR #${scan.pr_number}: ${escapeHtml(scan.pr_title)}
        <div class="history-meta">${escapeHtml(scan.created_at)} &bull; ${scan.reduction_pct}% context saved</div>
      </div>
      <span class="badge ${scan.drift_detected ? "badge-HIGH" : "badge-LOW"}">
        ${scan.drift_detected ? "DRIFT FOUND" : "IN SYNC"}
      </span>
    </div>
  `).join("");
}

async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    if (res.ok) {
      renderHistory(data.recent_scans, data.eval_metrics);
    }
  } catch (e) {
    // Ignore history load error on initial startup
  }
}

async function submitFeedback(issueId, rating, goodBtn, badBtn) {
  try {
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ issue_id: issueId, rating })
    });
    const data = await res.json();
    if (res.ok) {
      goodBtn.classList.toggle("active-good", rating === "accurate");
      badBtn.classList.toggle("active-bad", rating === "false_positive");
      renderHistory(data.recent_scans, data.eval_metrics);
    }
  } catch (e) {
    // Ignore transient feedback error
  }
}

async function runAnalysis(useSample = false) {
  errorBox.style.display = "none";
  results.style.display = "none";
  loader.style.display = "block";
  analyzeBtn.disabled = true;
  sampleBtn.disabled = true;

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pr_url: prUrlInput.value,
        use_sample: useSample
      })
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Failed to analyze Pull Request.");
    }

    document.getElementById("repoTitle").textContent = `${data.repo} — PR #${data.pr_number}`;
    document.getElementById("prSubtitle").textContent = data.pr_title;
    document.getElementById("retrievalPill").textContent =
      `Retrieved ${data.retrieval_stats.retrieved_count}/${data.retrieval_stats.total_chunks} doc sections (${data.retrieval_stats.reduction_pct}% context saved)`;
    document.getElementById("summaryBox").textContent = data.summary;

    const container = document.getElementById("issuesContainer");
    container.innerHTML = "";

    if (!data.issues || data.issues.length === 0) {
      container.innerHTML = `
        <div class="issue-card" style="border-color: var(--green-border); background: var(--green-bg);">
          <strong style="color: #aff5b4;">No documentation drift detected!</strong>
          <p style="color: var(--text); margin-top: 0.4rem; font-size: 0.9rem;">
            The retrieved Markdown documentation matches the code changes in this Pull Request.
          </p>
        </div>`;
    } else {
      data.issues.forEach((issue) => {
        const card = document.createElement("div");
        card.className = "issue-card";
        card.innerHTML = `
          <div class="issue-header">
            <span class="file-tag">${escapeHtml(issue.file_path)}</span>
            <span class="badge badge-${escapeHtml(issue.severity)}">${escapeHtml(issue.severity)} DRIFT</span>
          </div>
          <div class="reason">${escapeHtml(issue.reason)}</div>
          <div class="diff-grid">
            <div class="diff-pane diff-old">
              <span class="pane-label">- Outdated Documentation</span>${escapeHtml(issue.outdated_text)}
            </div>
            <div class="diff-pane diff-new">
              <span class="pane-label">+ Suggested Documentation Update</span>${escapeHtml(issue.suggested_fix)}
            </div>
          </div>
          <div class="card-actions">
            <button class="copy-btn" type="button">Copy Suggested Fix</button>
            <div class="eval-group">
              <span style="font-size: 0.78rem; color: var(--muted);">Eval:</span>
              <button class="eval-btn good-btn" type="button">👍 Accurate</button>
              <button class="eval-btn bad-btn" type="button">👎 False Positive</button>
            </div>
          </div>
        `;

        const copyBtn = card.querySelector(".copy-btn");
        copyBtn.addEventListener("click", () => {
          navigator.clipboard.writeText(issue.suggested_fix);
          copyBtn.textContent = "Copied!";
          setTimeout(() => (copyBtn.textContent = "Copy Suggested Fix"), 1500);
        });

        const goodBtn = card.querySelector(".good-btn");
        const badBtn = card.querySelector(".bad-btn");
        if (issue.id) {
          goodBtn.addEventListener("click", () => submitFeedback(issue.id, "accurate", goodBtn, badBtn));
          badBtn.addEventListener("click", () => submitFeedback(issue.id, "false_positive", goodBtn, badBtn));
        }

        container.appendChild(card);
      });
    }

    if (data.recent_scans) {
      renderHistory(data.recent_scans, data.eval_metrics);
    }

    results.style.display = "block";
  } catch (err) {
    errorBox.textContent = `Error: ${err.message}`;
    errorBox.style.display = "block";
  } finally {
    loader.style.display = "none";
    analyzeBtn.disabled = false;
    sampleBtn.disabled = false;
  }
}

analyzeBtn.addEventListener("click", () => runAnalysis(false));
sampleBtn.addEventListener("click", () => runAnalysis(true));
loadHistory();
