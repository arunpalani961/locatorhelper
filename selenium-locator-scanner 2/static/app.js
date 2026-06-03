// ============================================
// Simple Scan Mode
// ============================================
const form = document.querySelector("#scanForm");
const input = document.querySelector("#urlInput");
const button = document.querySelector("#scanButton");
const exportButton = document.querySelector("#exportButton");
const statusText = document.querySelector("#statusText");
const countText = document.querySelector("#countText");
const pageText = document.querySelector("#pageText");
const body = document.querySelector("#resultsBody");
const template = document.querySelector("#rowTemplate");

let latestRows = [];

function setStatus(message) {
  statusText.textContent = message;
}

function scoreClass(score) {
  if (score >= 85) return "high";
  if (score >= 60) return "medium";
  return "low";
}

function renderRows(rows, targetBody = body) {
  targetBody.innerHTML = "";
  if (!rows.length) {
    targetBody.innerHTML = '<tr class="empty-row"><td colspan="6">No visible target elements were found.</td></tr>';
    return;
  }

  for (const row of rows) {
    const node = template.content.cloneNode(true);
    node.querySelector(".element").textContent = row.element;
    node.querySelector(".text").textContent = row.text || "-";
    node.querySelector(".best-by").textContent = row.bestBy;
    node.querySelector(".best-value").textContent = row.bestValue;
    node.querySelector(".reason").textContent = row.reason;
    const score = node.querySelector(".score");
    score.textContent = `${row.confidence}%`;
    score.classList.add(scoreClass(row.confidence));
    node.querySelector(".java").textContent = row.java;

    const alternatives = node.querySelector(".alternatives");
    if (row.alternatives.length === 0) {
      node.querySelector("details").remove();
    } else {
      alternatives.innerHTML = row.alternatives
        .map((alt) => `<div><code>${escapeHtml(alt.by)}("${escapeHtml(alt.value)}")</code><small>${escapeHtml(alt.reason)}</small></div>`)
        .join("");
    }

    targetBody.appendChild(node);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function toCsv(rows) {
  const header = ["Element", "Text / Label", "Best Locator", "Value", "Confidence", "Java Example"];
  const lines = [header, ...rows.map((row) => [
    row.element,
    row.text,
    row.bestBy,
    row.bestValue,
    row.confidence,
    row.java
  ])];
  return lines
    .map((line) => line.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(","))
    .join("\n");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = input.value.trim();
  if (!url) return;

  button.disabled = true;
  exportButton.disabled = true;
  countText.textContent = "0";
  pageText.textContent = "Scanning...";
  setStatus("Opening page with Selenium...");
  renderRows([]);

  try {
    const response = await fetch("/api/scan", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ url })
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Scan failed");
    }

    latestRows = payload.rows;
    renderRows(latestRows);
    countText.textContent = String(payload.count);
    pageText.textContent = payload.title || payload.url;
    setStatus(`Completed in ${payload.durationMs} ms`);
    exportButton.disabled = latestRows.length === 0;
  } catch (error) {
    latestRows = [];
    renderRows([]);
    countText.textContent = "0";
    pageText.textContent = "Scan failed";
    setStatus(error.message);
  } finally {
    button.disabled = false;
  }
});

exportButton.addEventListener("click", () => {
  const blob = new Blob([toCsv(latestRows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "selenium-locators.csv";
  anchor.click();
  URL.revokeObjectURL(url);
});

// ============================================
// Session Multi-Page Mode
// ============================================
let currentSessionId = null;

const startSessionBtn = document.querySelector("#startSessionBtn");
const endSessionBtn = document.querySelector("#endSessionBtn");
const sessionIdText = document.querySelector("#sessionIdText");
const loginPanel = document.querySelector("#loginPanel");
const navigationPanel = document.querySelector("#navigationPanel");
const sessionStatus = document.querySelector("#sessionStatus");
const sessionStatusText = document.querySelector("#sessionStatusText");
const sessionPageText = document.querySelector("#sessionPageText");
const sessionCountText = document.querySelector("#sessionCountText");
const sessionResults = document.querySelector("#sessionResults");
const sessionResultsBody = document.querySelector("#sessionResultsBody");

const loginUrlInput = document.querySelector("#loginUrl");
const usernameSelectorInput = document.querySelector("#usernameSelector");
const usernameValueInput = document.querySelector("#usernameValue");
const passwordSelectorInput = document.querySelector("#passwordSelector");
const passwordValueInput = document.querySelector("#passwordValue");
const loginButtonSelectorInput = document.querySelector("#loginButtonSelector");
const performLoginBtn = document.querySelector("#performLoginBtn");

const navigateUrlInput = document.querySelector("#navigateUrl");
const navigateBtn = document.querySelector("#navigateBtn");
const clickSelectorInput = document.querySelector("#clickSelector");
const clickBtn = document.querySelector("#clickBtn");
const scanSessionBtn = document.querySelector("#scanSessionBtn");

// Tab switching - ensure it works even if DOM is ready
function initTabSwitching() {
  try {
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");
    
    if (tabBtns.length === 0) {
      setTimeout(initTabSwitching, 100);
      return;
    }
    
    tabBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const tabName = btn.dataset.tab;
        
        tabBtns.forEach((b) => b.classList.remove("active"));
        tabContents.forEach((c) => c.classList.remove("active"));
        
        btn.classList.add("active");
        const tabElement = document.querySelector(`#${tabName}-tab`);
        if (tabElement) {
          tabElement.classList.add("active");
        }
      });
    });
  } catch (error) {
    console.error("Error initializing tab switching:", error);
    setTimeout(initTabSwitching, 100);
  }
}

// Initialize immediately and also on DOMContentLoaded
initTabSwitching();
document.addEventListener("DOMContentLoaded", initTabSwitching);

// Session management
startSessionBtn.addEventListener("click", async () => {
  startSessionBtn.disabled = true;
  sessionStatusText.textContent = "Starting...";
  sessionStatus.style.display = "";
  
  try {
    const response = await fetch("/api/session/start", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({})
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    
    currentSessionId = payload.session_id;
    sessionIdText.textContent = `Session: ${currentSessionId.slice(0, 8)}...`;
    sessionStatusText.textContent = "Session Active";
    
    // Show login panel
    loginPanel.style.display = "";
    navigationPanel.style.display = "none";
    sessionResults.style.display = "none";
    
    endSessionBtn.disabled = false;
    startSessionBtn.style.display = "none";
  } catch (error) {
    sessionStatusText.textContent = `Error: ${error.message}`;
    startSessionBtn.disabled = false;
  }
});

performLoginBtn.addEventListener("click", async () => {
  if (!currentSessionId) return;
  
  performLoginBtn.disabled = true;
  sessionStatusText.textContent = "Logging in...";
  
  try {
    const loginUrl = loginUrlInput.value.trim();
    const usernameSelector = usernameSelectorInput.value.trim();
    const username = usernameValueInput.value.trim();
    const passwordSelector = passwordSelectorInput.value.trim();
    const password = passwordValueInput.value.trim();
    const loginButtonSelector = loginButtonSelectorInput.value.trim();
    
    if (!loginUrl || !usernameSelector || !username || !passwordSelector || !password) {
      throw new Error("Please fill all login fields");
    }
    
    // Navigate to login page
    let response = await fetch("/api/session/navigate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        url: loginUrl
      })
    });
    let payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    
    // Fill username
    response = await fetch("/api/session/fill", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        selector: usernameSelector,
        value: username
      })
    });
    payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    
    // Fill password
    response = await fetch("/api/session/fill", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        selector: passwordSelector,
        value: password
      })
    });
    payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    
    // Click login button
    response = await fetch("/api/session/click", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        selector: loginButtonSelector
      })
    });
    payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    
    sessionStatusText.textContent = "Logged in successfully";
    sessionPageText.textContent = payload.title || payload.url;
    
    // Show navigation panel
    loginPanel.style.display = "none";
    navigationPanel.style.display = "";
    sessionResults.style.display = "none";
  } catch (error) {
    sessionStatusText.textContent = `Error: ${error.message}`;
  } finally {
    performLoginBtn.disabled = false;
  }
});

navigateBtn.addEventListener("click", async () => {
  if (!currentSessionId) return;
  
  navigateBtn.disabled = true;
  sessionStatusText.textContent = "Navigating...";
  
  try {
    const url = navigateUrlInput.value.trim();
    if (!url) throw new Error("Please enter a URL");
    
    const response = await fetch("/api/session/navigate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        url
      })
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    
    sessionStatusText.textContent = "Navigated";
    sessionPageText.textContent = payload.title || payload.url;
    sessionResults.style.display = "none";
    renderRows([], sessionResultsBody);
  } catch (error) {
    sessionStatusText.textContent = `Error: ${error.message}`;
  } finally {
    navigateBtn.disabled = false;
  }
});

clickBtn.addEventListener("click", async () => {
  if (!currentSessionId) return;
  
  clickBtn.disabled = true;
  sessionStatusText.textContent = "Clicking element...";
  
  try {
    const selector = clickSelectorInput.value.trim();
    if (!selector) throw new Error("Please enter a CSS selector");
    
    const response = await fetch("/api/session/click", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        selector
      })
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    
    sessionStatusText.textContent = "Element clicked";
    sessionPageText.textContent = payload.title || payload.url;
    sessionResults.style.display = "none";
    renderRows([], sessionResultsBody);
  } catch (error) {
    sessionStatusText.textContent = `Error: ${error.message}`;
  } finally {
    clickBtn.disabled = false;
  }
});

scanSessionBtn.addEventListener("click", async () => {
  if (!currentSessionId) return;
  
  scanSessionBtn.disabled = true;
  sessionStatusText.textContent = "Scanning page...";
  sessionCountText.textContent = "0";
  
  try {
    const response = await fetch("/api/session/scan", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId
      })
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    
    renderRows(payload.rows, sessionResultsBody);
    sessionCountText.textContent = String(payload.count);
    sessionPageText.textContent = payload.title || payload.url;
    sessionStatusText.textContent = "Scan complete";
    sessionResults.style.display = "";
  } catch (error) {
    sessionStatusText.textContent = `Error: ${error.message}`;
  } finally {
    scanSessionBtn.disabled = false;
  }
});

endSessionBtn.addEventListener("click", async () => {
  if (!currentSessionId) return;
  
  endSessionBtn.disabled = true;
  
  try {
    const response = await fetch("/api/session/end", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId
      })
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error);
    
    currentSessionId = null;
    sessionStatusText.textContent = "Session ended";
    sessionIdText.textContent = "";
    
    // Reset UI
    loginPanel.style.display = "none";
    navigationPanel.style.display = "none";
    sessionResults.style.display = "none";
    sessionStatus.style.display = "none";
    
    startSessionBtn.style.display = "";
    startSessionBtn.disabled = false;
  } catch (error) {
    sessionStatusText.textContent = `Error: ${error.message}`;
  }
});

