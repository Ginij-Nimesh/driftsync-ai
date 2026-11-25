document.getElementById("analyzeBtn").addEventListener("click", function () {
  runAnalysis(false);
});

document.getElementById("sampleBtn").addEventListener("click", function () {
  runAnalysis(true);
});

async function runAnalysis(useSample) {
  const prUrl = document.getElementById("prUrl").value.trim();
  const errorBox = document.getElementById("errorBox");
  const loader = document.getElementById("loader");
  const results = document.getElementById("results");

  errorBox.style.display = "none";
  results.style.display = "none";
  loader.style.display = "block";
  document.getElementById("analyzeBtn").disabled = true;
  document.getElementById("sampleBtn").disabled = true;

  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pr_url: prUrl, use_sample: useSample })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Analysis failed.");

    renderResults(data);
  } catch (err) {
    errorBox.textContent = "Error: " + err.message;
    errorBox.style.display = "block";
  } finally {
    loader.style.display = "none";
    document.getElementById("analyzeBtn").disabled = false;
    document.getElementById("sampleBtn").disabled = false;
  }
}

function renderResults(data) {
  document.getElementById("repoTitle").textContent = data.repo + " — PR #" + data.pr_number;
  document.getElementById("prSubtitle").textContent = data.pr_title;

  const stats = data.retrieval_stats;
  document.getElementById("retrievalPill").textContent =
    "Retrieved " + stats.retrieved_count + "/" + stats.total_chunks + " doc sections (" + stats.reduction_pct + "% context saved)";

  document.getElementById("summaryBox").innerHTML =
    "<strong>AI Audit Summary:</strong> " + escapeHtml(data.analysis.summary);

  const container = document.getElementById("issuesContainer");
  container.innerHTML = "";

  const issues = data.analysis.issues || [];
  if (issues.length === 0) {
    container.innerHTML = '<div class="issue-card" style="border-color: var(--green-border); color: #aff5b4;">No documentation drift detected! Your Markdown files align with this Pull Request.</div>';
  } else {
    issues.forEach(function (issue, idx) {
      const card = document.createElement("div");
      card.className = "issue-card";
      card.innerHTML =
        '<div class="issue-header">' +
          '<span class="file-tag">📄 ' + escapeHtml(issue.file_path) + '</span>' +
          '<span class="badge badge-' + escapeHtml(issue.severity) + '">' + escapeHtml(issue.severity) + ' DRIFT</span>' +
        '</div>' +
        '<div class="reason">' + escapeHtml(issue.reason) + '</div>' +
        '<div class="diff-grid">' +
          '<div class="diff-pane diff-old">' +
            '<span class="pane-label" style="color:#ff7b72;">- Outdated Documentation</span>' + escapeHtml(issue.outdated_text) +
          '</div>' +
          '<div class="diff-pane diff-new">' +
            '<span class="pane-label" style="color:#3fb950;">+ Suggested Replacement</span><span id="fix-' + idx + '">' + escapeHtml(issue.suggested_fix) + '</span>' +
          '</div>' +
        '</div>' +
        '<button class="copy-btn" type="button" onclick="copyFix(' + idx + ', this)">Copy Suggested Fix</button>';
      container.appendChild(card);
    });
  }

  document.getElementById("results").style.display = "block";
}

function copyFix(idx, btn) {
  const text = document.getElementById("fix-" + idx).textContent;
  navigator.clipboard.writeText(text);
  btn.textContent = "Copied!";
  setTimeout(function () { btn.textContent = "Copy Suggested Fix"; }, 1500);
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
