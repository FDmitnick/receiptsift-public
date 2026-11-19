(() => {
  "use strict";

  const consentKey = "receiptsift_analytics_consent";
  const visitorKey = "receiptsift_analytics_visitor";
  const legacyConsentKey = "clearledger_analytics_consent";
  const legacyVisitorKey = "clearledger_analytics_visitor";
  const allowedPaths = new Set(["/app", "/register", "/pricing", "/login", "/account"]);
  let consent = localStorage.getItem(consentKey) || localStorage.getItem(legacyConsentKey);

  function chinese() {
    return (localStorage.getItem("receiptsift-language") || localStorage.getItem("receiptsift-site-language") || "en").startsWith("zh");
  }

  function visitorId() {
    let value = localStorage.getItem(visitorKey) || localStorage.getItem(legacyVisitorKey);
    if (!value) {
      value = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
      localStorage.setItem(visitorKey, value);
    }
    return value;
  }

  function source() {
    const query = new URLSearchParams(location.search);
    const campaign = ["utm_source", "utm_medium", "utm_campaign"].map((key) => query.get(key)).filter(Boolean).join(" / ");
    if (campaign) return campaign.slice(0, 300);
    if (!document.referrer) return null;
    try {
      const referrer = new URL(document.referrer);
      return `${referrer.hostname}${referrer.pathname}`.slice(0, 300);
    } catch (_) {
      return null;
    }
  }

  function send(event, properties = {}) {
    if (consent !== "granted" || location.pathname === "/admin") return;
    fetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      keepalive: true,
      body: JSON.stringify({
        event,
        visitor_id: visitorId(),
        path: location.pathname,
        source: source(),
        properties,
      }),
    }).catch(() => {});
  }

  function recordPage() {
    send("page_view", { title: document.title.slice(0, 120) });
    if (location.pathname === "/pricing") send("pricing_view");
  }

  function setConsent(value) {
    consent = value;
    localStorage.setItem(consentKey, value);
    document.querySelector("#receiptsiftConsent")?.remove();
    if (value === "granted") recordPage();
    renderPreferenceControl();
  }

  function consentBanner() {
    if (consent || location.pathname === "/admin") return;
    const banner = document.createElement("section");
    banner.id = "receiptsiftConsent";
    const locale = window.ReceiptSiftLocale;
    const text = (en, zh) => locale?.t(en, zh) || en;
    banner.setAttribute("aria-label", text("Analytics preference", "匿名统计偏好"));
    banner.innerHTML = `
      <div><strong>${text("Privacy-friendly analytics", "尊重隐私的匿名统计")}</strong><p>${text("Allow anonymous page and product-click measurement. We do not store raw IP addresses, browser fingerprints, or receipt contents.", "允许匿名统计页面访问与产品点击。我们不保存原始 IP、浏览器指纹或凭证内容。")}</p></div>
      <div class="cl-consent-actions"><button type="button" data-consent="denied">${text("Decline", "拒绝")}</button><button type="button" data-consent="granted">${text("Allow analytics", "允许匿名统计")}</button></div>`;
    const style = document.createElement("style");
    style.textContent = `
      #receiptsiftConsent{position:fixed;z-index:9999;left:20px;right:20px;bottom:20px;display:flex;align-items:center;justify-content:space-between;gap:24px;max-width:920px;margin:auto;padding:18px 20px;background:#1d1d1f;color:#f5f5f7;border:1px solid #424245;box-shadow:0 12px 40px rgba(0,0,0,.2);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
      #receiptsiftConsent strong{font-size:15px}#receiptsiftConsent p{margin:4px 0 0;color:#d2d2d7}.cl-consent-actions{display:flex;gap:8px;flex:none}.cl-consent-actions button,.cl-analytics-preference{min-height:38px;padding:8px 14px;border:1px solid #86868b;border-radius:999px;background:transparent;color:inherit;cursor:pointer;font:inherit}.cl-consent-actions button:last-child{background:#f5f5f7;color:#1d1d1f;border-color:#f5f5f7}.cl-analytics-preference{color:#1d1d1f;margin-top:12px}@media(max-width:680px){#receiptsiftConsent{left:10px;right:10px;bottom:10px;align-items:stretch;flex-direction:column}.cl-consent-actions{width:100%}.cl-consent-actions button{flex:1}}`;
    document.head.appendChild(style);
    banner.addEventListener("click", (event) => {
      const button = event.target.closest("[data-consent]");
      if (button) setConsent(button.dataset.consent);
    });
    document.body.appendChild(banner);
    locale?.apply(banner);
  }

  function consentCopy() {
    return chinese()
      ? `<div><strong>保护隐私的使用分析</strong><p>允许匿名统计页面访问和产品点击。我们不保存原始 IP 地址、浏览器指纹或单据内容。</p></div><div class="cl-consent-actions"><button type="button" data-consent="denied">拒绝</button><button type="button" data-consent="granted">允许分析</button></div>`
      : `<div><strong>Privacy-friendly analytics</strong><p>Allow anonymous page and product-click measurement. We do not store raw IP addresses, browser fingerprints, or receipt contents.</p></div><div class="cl-consent-actions"><button type="button" data-consent="denied">Decline</button><button type="button" data-consent="granted">Allow analytics</button></div>`;
  }

  function refreshLanguage() {
    const banner = document.querySelector("#receiptsiftConsent");
    if (!banner) return;
    banner.setAttribute("aria-label", chinese() ? "分析偏好" : "Analytics preference");
    banner.innerHTML = consentCopy();
  }

  function renderPreferenceControl() {
    if (location.pathname !== "/cookies") return;
    const existing = document.querySelector("#analyticsPreferenceButton");
    if (existing) {
      existing.textContent = `Analytics: ${consent === "granted" ? "allowed" : "declined"}. Change preference`;
      return;
    }
    const button = document.createElement("button");
    button.id = "analyticsPreferenceButton";
    button.className = "cl-analytics-preference";
    button.type = "button";
    button.textContent = `Analytics: ${consent === "granted" ? "allowed" : consent === "denied" ? "declined" : "not selected"}. Change preference`;
    button.addEventListener("click", () => {
      localStorage.removeItem(consentKey);
      consent = null;
      consentBanner();
    });
    document.querySelector(".legal-callout")?.insertAdjacentElement("afterend", button);
  }

  document.addEventListener("click", (event) => {
    const element = event.target.closest("a,button");
    if (!element) return;
    let target = element.id || element.getAttribute("href") || "";
    let pathname = "";
    if (target.startsWith("/")) pathname = target.split("?", 1)[0];
    const important = element.dataset.track || allowedPaths.has(pathname) || /cta|action|primary/i.test(element.className || "") || /subscribe|sample|upload|register|login/i.test(element.id || "");
    if (!important) return;
    send("cta_click", {
      label: (element.dataset.track || element.getAttribute("aria-label") || element.textContent || element.id).trim().slice(0, 80),
      target: target.slice(0, 160),
    });
  }, true);

  document.addEventListener("submit", (event) => {
    if (event.target.id === "registerForm") send("registration_started");
    if (event.target.id === "loginForm") send("login_started");
  }, true);

  window.ReceiptSiftAnalytics = { send, setConsent, refreshLanguage };
  if (consent === "granted") recordPage();
  consentBanner();
  renderPreferenceControl();
})();
