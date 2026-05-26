console.log("DLP Guardian loaded");

let scanTimeout = null;
let warningShown = false;

function attachListeners() {
  const inputs = document.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"]');
  inputs.forEach(el => {
    if (el.dataset.dlpAttached) return;
    el.dataset.dlpAttached = "true";

    // Scan on every keystroke with debounce
    el.addEventListener("input", function() {
      clearTimeout(scanTimeout);
      scanTimeout = setTimeout(async () => {
        const text = el.value || el.innerText || el.textContent || "";
        if (text.trim().length < 10) return;
        const findings = await scanText(text);
        if (findings.length > 0 && !warningShown) {
          warningShown = true;
          showWarning(findings, el);
        }
      }, 800); // wait 800ms after user stops typing
    }, true);

    // Also intercept Enter and click on send buttons
    el.addEventListener("keydown", async function(e) {
      if (e.key === "Enter" && !e.shiftKey) {
        const text = el.value || el.innerText || el.textContent || "";
        if (text.trim().length < 5) return;
        const findings = await scanText(text);
        if (findings.length > 0) {
          e.preventDefault();
          e.stopImmediatePropagation();
          warningShown = true;
          showWarning(findings, el);
        }
      }
    }, true);
  });
}

// Run immediately and watch for new elements
attachListeners();
setInterval(attachListeners, 2000); // re-scan DOM every 2s for new inputs

async function scanText(text) {
  try {
    const res = await fetch("http://localhost:5000/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    return await res.json();
  } catch(err) {
    return [];
  }
}

function showWarning(findings, inputEl) {
  document.getElementById("dlp-warning")?.remove();

  const colors = {
    EMAIL: "#f59e0b", API_KEY: "#ef4444",
    CREDIT_CARD: "#ef4444", SSN: "#ef4444",
    PHONE: "#f59e0b", PASSWORD: "#ef4444",
    NAME: "#a78bfa", ADDRESS: "#60a5fa"
  };

  const rows = findings.map(f => `
    <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #2a2a3e;">
      <span style="color:${colors[f.entity] || "#a78bfa"};font-weight:700;">${f.entity}</span>
      <span style="color:#94a3b8;font-size:12px;">"${f.value}" — ${Math.round(f.confidence * 100)}%</span>
    </div>
  `).join("");

  const div = document.createElement("div");
  div.id = "dlp-warning";
  div.style.cssText = "position:fixed;top:20px;right:20px;z-index:2147483647;background:#1e1e2e;border:2px solid #ef4444;border-radius:12px;padding:16px;width:320px;font-family:sans-serif;box-shadow:0 8px 32px rgba(239,68,68,0.3);";
  div.innerHTML = `
    <div style="color:#ef4444;font-weight:700;font-size:14px;margin-bottom:10px;">
      ⚠️ Sensitive Data Detected
    </div>
    ${rows}
    <div style="display:flex;gap:8px;margin-top:12px;">
      <button id="dlp-cancel" style="flex:1;padding:8px;background:#ef4444;color:white;border:none;border-radius:8px;cursor:pointer;font-size:13px;">✋ Don't Send</button>
      <button id="dlp-allow" style="flex:1;padding:8px;background:#374151;color:white;border:none;border-radius:8px;cursor:pointer;font-size:13px;">Send Anyway</button>
    </div>
  `;

  document.body.appendChild(div);

  document.getElementById("dlp-cancel").onclick = () => {
    div.remove();
    warningShown = false;
    if (inputEl) {
      inputEl.value = "";
      inputEl.innerText = "";
    }
  };

  document.getElementById("dlp-allow").onclick = () => {
    div.remove();
    warningShown = false;
  };
}
