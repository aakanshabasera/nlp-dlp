console.log("DLP Guardian loaded");

let scanTimeout = null;
let warningShown = false;

function attachListeners() {
  const inputs = document.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"]');
  inputs.forEach(el => {
    if (el.dataset.dlpAttached) return;
    el.dataset.dlpAttached = "true";

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
      }, 800);
    }, true);

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

attachListeners();
setInterval(attachListeners, 2000);

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

function injectStyles() {
  if (document.getElementById("dlp-styles")) return;
  const style = document.createElement("style");
  style.id = "dlp-styles";
  style.textContent = `
    @keyframes dlp-in {
      from { opacity:0; transform:translateY(-6px) scale(0.98); }
      to   { opacity:1; transform:translateY(0)    scale(1);    }
    }
    @keyframes dlp-out {
      from { opacity:1; transform:translateY(0)    scale(1);    }
      to   { opacity:0; transform:translateY(-6px) scale(0.98); }
    }
    @keyframes dlp-row {
      from { opacity:0; transform:translateX(-5px); }
      to   { opacity:1; transform:translateX(0); }
    }
    #dlp-warning * {
      box-sizing:border-box;
      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
    }
    #dlp-warning .dlp-stop {
      background:#fde8d0; color:#8a3010;
      border:1px solid #f5c4a0;
      transition:background 0.15s,transform 0.1s;
      cursor:pointer;
    }
    #dlp-warning .dlp-stop:hover { background:#f5d0b0; transform:scale(1.02); }
    #dlp-warning .dlp-allow {
      background:#fff; color:#a08070;
      border:1px solid #ede8df;
      transition:background 0.15s,transform 0.1s;
      cursor:pointer;
    }
    #dlp-warning .dlp-allow:hover { background:#fdfaf6; transform:scale(1.02); }
    #dlp-warning .dlp-x {
      background:none; border:none;
      color:#c4b0a0; cursor:pointer; font-size:13px;
      padding:2px 5px; border-radius:4px;
      transition:background 0.15s,color 0.15s;
    }
    #dlp-warning .dlp-x:hover { background:#f0ece6; color:#6a4030; }
  `;
  document.head.appendChild(style);
}

function showWarning(findings, inputEl) {
  document.getElementById("dlp-warning")?.remove();
  injectStyles();

  const meta = {
    API_KEY:     { bg:"#fff0ee", border:"#f5c4ba", dot:"#f87171", label:"API Key" },
    PASSWORD:    { bg:"#fff0ee", border:"#f5c4ba", dot:"#f87171", label:"Password" },
    CREDIT_CARD: { bg:"#fff0ee", border:"#f5c4ba", dot:"#f87171", label:"Credit Card" },
    SSN:         { bg:"#fff0ee", border:"#f5c4ba", dot:"#f87171", label:"SSN" },
    EMAIL:       { bg:"#fff8ec", border:"#f5dfa0", dot:"#fbbf24", label:"Email" },
    PHONE:       { bg:"#fff8ec", border:"#f5dfa0", dot:"#fbbf24", label:"Phone" },
    NAME:        { bg:"#f5f0ff", border:"#d4c4f5", dot:"#a78bfa", label:"Name" },
    ADDRESS:     { bg:"#eef4ff", border:"#b8cff5", dot:"#60a5fa", label:"Address" },
  };

  const isHigh = findings.some(f => ["API_KEY","CREDIT_CARD","SSN","PASSWORD"].includes(f.entity));

  const rows = findings.map((f, i) => {
    const m = meta[f.entity] || meta.NAME;
    const pct = Math.round(f.confidence * 100);
    return `
      <div style="
        display:flex;align-items:center;gap:8px;
        padding:6px 10px;border-radius:7px;
        background:${m.bg};border:1px solid ${m.border};
        animation:dlp-row 0.2s ease ${i * 0.06 + 0.08}s both;
      ">
        <div style="width:5px;height:5px;border-radius:50%;background:${m.dot};flex-shrink:0;"></div>
        <span style="font-size:11px;font-weight:600;color:#4a2010;flex-shrink:0;">${m.label}</span>
        <span style="flex:1;font-size:11px;color:#a08070;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">"${f.value}"</span>
        <span style="font-size:10px;color:#c4b0a0;flex-shrink:0;">${pct}%</span>
      </div>
    `;
  }).join("");

  const div = document.createElement("div");
  div.id = "dlp-warning";
  div.style.cssText = `
    position:fixed; top:18px; right:18px;
    z-index:2147483647; width:310px;
    background:#fdfaf6;
    border:1px solid #ede8df;
    border-radius:14px; padding:15px;
    box-shadow:0 4px 20px rgba(80,40,20,0.10),0 1px 4px rgba(80,40,20,0.06);
    animation:dlp-in 0.25s cubic-bezier(0.22,1,0.36,1);
  `;

  div.innerHTML = `
    <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:11px;">
      <div style="display:flex;align-items:center;gap:8px;">
        <div style="width:30px;height:30px;border-radius:8px;background:#fde8d0;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;">🛡️</div>
        <div>
          <div style="font-size:12px;font-weight:600;color:#2c1810;">Sensitive data found</div>
          <div style="font-size:10px;color:#a08070;margin-top:1px;">${findings.length} item${findings.length > 1 ? "s" : ""} · ${isHigh ? "High risk" : "Medium risk"}</div>
        </div>
      </div>
      <button class="dlp-x" id="dlp-close">✕</button>
    </div>

    <div style="display:flex;flex-direction:column;gap:4px;margin-bottom:12px;">
      ${rows}
    </div>

    <div style="height:1px;background:#ede8df;margin-bottom:11px;"></div>

    <div style="display:flex;gap:6px;">
      <button id="dlp-cancel" class="dlp-stop" style="flex:1;padding:8px;border-radius:8px;font-size:12px;font-weight:600;">Don't send</button>
      <button id="dlp-allow" class="dlp-allow" style="flex:1;padding:8px;border-radius:8px;font-size:12px;font-weight:500;">Send anyway</button>
    </div>
  `;

  document.body.appendChild(div);

  function dismiss(cb) {
    div.style.animation = "dlp-out 0.18s ease forwards";
    setTimeout(() => { div.remove(); cb && cb(); }, 170);
  }

  document.getElementById("dlp-close").onclick  = () => dismiss(() => { warningShown = false; });
  document.getElementById("dlp-allow").onclick  = () => dismiss(() => { warningShown = false; });
  document.getElementById("dlp-cancel").onclick = () => dismiss(() => {
    warningShown = false;
    if (inputEl) { inputEl.value = ""; inputEl.innerText = ""; }
  });
}
