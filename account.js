const accountEmail = document.querySelector("#accountEmail");
const accountCreated = document.querySelector("#accountCreated");
const exportStatus = document.querySelector("#exportStatus");
const deleteStatus = document.querySelector("#deleteStatus");
const billingStatus = document.querySelector("#billingStatus");
const diagnosticCaseStatus = document.querySelector("#diagnosticCaseStatus");
const historyStatus = document.querySelector("#historyStatus");
const ledgerStatus = document.querySelector("#ledgerStatus");
const locale = window.ReceiptSiftLocale;
const tr = (en, zh) => locale?.t(en, zh) || en;

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}

function formatDate(value) {
  return new Date(value).toLocaleString(locale?.locales?.[locale.get()]?.htmlLang || "en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

function formatMoney(total, currency) {
  if (total == null || total === "") return tr("Amount unavailable", "金额未知");
  try { return new Intl.NumberFormat(locale?.locales?.[locale.get()]?.htmlLang || "en-US", { style: "currency", currency: currency || "USD" }).format(Number(total)); }
  catch (_) { return `${currency || ""} ${total}`.trim(); }
}

function renderRecentHistory(payload) {
  const container = document.querySelector("#recentHistoryList");
  if (!payload.documents.length) {
    container.innerHTML = `<p class="case-empty">${tr("No documents in the last 7 days.", "最近 7 天还没有单据。")}</p>`;
    return;
  }
  container.innerHTML = payload.documents.map((item) => {
    const source = item.source_type === "batch" ? tr(`Batch · ${item.batch_name || "Untitled"}`, `批量 · ${item.batch_name || "未命名"}`) : tr("Single document", "单份解析");
    const documentType = ({ receipt: tr("Receipt", "收据"), invoice: tr("Invoice", "发票"), bill: tr("Bill", "账单") })[item.document_type] || tr("Document", "单据");
    const openUrl = item.source_type === "batch" ? `/batches?batch=${encodeURIComponent(item.batch_id || "")}&document=${encodeURIComponent(item.id)}` : `/app?history=${encodeURIComponent(item.id)}`;
    const deleteAction = item.source_type === "single" ? `<button class="delete-action" type="button" data-delete-history="${escapeHtml(item.id)}">${tr("Delete now", "立即删除")}</button>` : "";
    const keepLabel = item.ledger_entry_id ? tr("Saved", "已沉淀") : tr("Keep in ledger", "沉淀到台账");
    return `<article class="history-row">
      <div><b>${escapeHtml(item.merchant || item.filename)}</b><span>${escapeHtml(source)} · ${escapeHtml(documentType)}</span><small>${escapeHtml(item.filename)}</small></div>
      <div><b>${escapeHtml(formatMoney(item.total, item.currency))}</b><span>${escapeHtml(item.date || tr("Date unavailable", "日期未知"))}</span></div>
      <div><span>${tr("Created", "创建于")} ${escapeHtml(formatDate(item.created_at))}</span><small>${tr("Deletes", "自动删除于")} ${escapeHtml(formatDate(item.history_expires_at))}</small></div>
      <div class="history-actions"><a href="${openUrl}">${tr("Open", "打开")}</a><button class="keep-action" type="button" data-promote-source="${item.source_type}" data-promote-id="${escapeHtml(item.id)}" ${item.ledger_entry_id ? "disabled" : ""}>${keepLabel}</button>${deleteAction}</div>
    </article>`;
  }).join("");
}

function renderLedger(payload) {
  const container = document.querySelector("#ledgerList");
  if (!payload.entries.length) {
    container.innerHTML = `<p class="case-empty">${tr("No confirmed ledger entries yet.", "还没有确认沉淀的台账数据。")}</p>`;
    return;
  }
  container.innerHTML = payload.entries.map((item) => `<article class="history-row">
    <div><b>${escapeHtml(item.merchant || item.filename)}</b><span>${tr("Saved structured data", "已保存结构化数据")}</span><small>${escapeHtml(item.filename)}</small></div>
    <div><b>${escapeHtml(formatMoney(item.total, item.currency))}</b><span>${escapeHtml(item.date || tr("Date unavailable", "日期未知"))}</span></div>
    <div><span>${tr("Confirmed", "确认于")} ${escapeHtml(formatDate(item.created_at))}</span><small>${tr("Source", "来源")} ${escapeHtml(item.source_type === "batch" ? tr("Batch", "批量") : tr("Single document", "单份解析"))}</small></div>
    <div class="history-actions"><button class="delete-action" type="button" data-delete-ledger="${escapeHtml(item.entry_id)}">${tr("Delete ledger entry", "删除台账记录")}</button></div>
  </article>`).join("");
}

function renderDiagnosticCases(payload) {
  const container = document.querySelector("#diagnosticCaseList");
  if (!payload.available && !payload.cases.length) {
    container.innerHTML = `<p class="case-empty">${tr("Secure diagnostic reporting is not configured.", "安全诊断报告尚未配置。")}</p>`;
    return;
  }
  if (!payload.cases.length) {
    container.innerHTML = `<p class="case-empty">${tr("No diagnostic evidence is stored for this account.", "该账户没有存储诊断证据。")}</p>`;
    return;
  }
  container.innerHTML = payload.cases.map((item) => `<article class="case-row">
    <div><b>${escapeHtml(item.case_id.slice(0, 12))}</b><small>${tr("Order", "订单")} ${escapeHtml(item.order_id.slice(0, 12))}</small></div>
    <div><span>${item.has_source_pdf ? tr("Encrypted PDF attached", "已附加加密 PDF") : tr("Result data only", "仅结果数据")}</span><small>${tr("Submitted", "提交于")} ${formatDate(item.created_at)}</small></div>
    <div><span>${tr("Deletes automatically", "自动删除")}</span><small>${formatDate(item.expires_at)}</small></div>
    <button type="button" data-delete-case="${escapeHtml(item.case_id)}">${tr("Delete now", "立即删除")}</button>
  </article>`).join("");
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 401) {
    location.replace(`/login?next=${encodeURIComponent(location.pathname)}`);
    throw new Error(tr("Authentication required", "需要登录。"));
  }
  if (!response.ok) {
    let message = tr("Request failed.", "请求失败。");
    try { message = (await response.json()).error?.message || message; } catch (_) { /* non-JSON */ }
    throw new Error(message);
  }
  return response;
}

async function loadAccount() {
  const [profileResponse, usageResponse, billingResponse, diagnosticsResponse, historyResponse, ledgerResponse] = await Promise.all([
    request("/api/v1/account"),
    request("/api/v1/account/usage"),
    request("/api/billing/me"),
    request("/api/v1/diagnostic-cases"),
    request("/api/v1/history"),
    request("/api/v1/ledger"),
  ]);
  const profile = await profileResponse.json();
  const usage = await usageResponse.json();
  const billing = await billingResponse.json();
  const diagnostics = await diagnosticsResponse.json();
  const history = await historyResponse.json();
  const ledger = await ledgerResponse.json();
  accountEmail.textContent = profile.email;
  document.querySelector("#operationsLink").classList.toggle("hidden", !profile.is_admin);
  accountCreated.textContent = `${tr("Member since", "加入于")} ${new Date(profile.created_at).toLocaleDateString(locale?.locales?.[locale.get()]?.htmlLang || "en-US", { month: "long", day: "numeric", year: "numeric" })}`;
  document.querySelector("#documentsParsed").textContent = usage.documents_parsed;
  document.querySelector("#pagesProcessed").textContent = usage.pages_processed;
  document.querySelector("#csvExports").textContent = usage.csv_exports;
  const entitlement = billing.entitlement;
  const isPaid = entitlement.plan !== "free";
  const isPro = entitlement.plan === "pro";
  document.querySelector("#billingPlan").textContent = entitlement.plan[0].toUpperCase() + entitlement.plan.slice(1);
  const allowanceCopy = {
    zh: `本月已使用 ${entitlement.documents_used} / ${entitlement.monthly_document_limit} 份 PDF · 剩余 ${entitlement.documents_remaining} 份 · 已使用 ${entitlement.pages_used} / ${entitlement.monthly_page_limit} 页 · 剩余 ${entitlement.pages_remaining} 页`,
    hi: `इस माह ${entitlement.documents_used} / ${entitlement.monthly_document_limit} PDF उपयोग हुए · ${entitlement.documents_remaining} शेष · ${entitlement.pages_used} / ${entitlement.monthly_page_limit} पृष्ठ उपयोग हुए · ${entitlement.pages_remaining} शेष`,
    es: `${entitlement.documents_used} de ${entitlement.monthly_document_limit} PDF usados este mes · ${entitlement.documents_remaining} restantes · ${entitlement.pages_used} de ${entitlement.monthly_page_limit} páginas usadas · ${entitlement.pages_remaining} restantes`,
    ar: `تم استخدام ${entitlement.documents_used} من ${entitlement.monthly_document_limit} ملف PDF هذا الشهر · المتبقي ${entitlement.documents_remaining} · تم استخدام ${entitlement.pages_used} من ${entitlement.monthly_page_limit} صفحة · المتبقي ${entitlement.pages_remaining}`,
  };
  document.querySelector("#billingAllowance").textContent = allowanceCopy[locale?.get()] || `${entitlement.documents_used} of ${entitlement.monthly_document_limit} PDFs used this month · ${entitlement.documents_remaining} remaining · ${entitlement.pages_used} of ${entitlement.monthly_page_limit} pages used · ${entitlement.pages_remaining} pages remaining`;
  document.querySelector("#upgradePlanLink").classList.toggle("hidden", isPro);
  document.querySelector("#cancelSubscriptionButton").classList.toggle("hidden", !isPaid);
  renderDiagnosticCases(diagnostics);
  renderRecentHistory(history);
  renderLedger(ledger);
}

document.querySelector("#recentHistoryList").addEventListener("click", async (event) => {
  const promote = event.target.closest("[data-promote-id]");
  const remove = event.target.closest("[data-delete-history]");
  if (promote) {
    promote.disabled = true;
    historyStatus.textContent = tr("Saving reviewed fields to your ledger…", "正在把核对后的字段沉淀到长期台账……");
    try {
      await request("/api/v1/ledger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_type: promote.dataset.promoteSource, document_id: promote.dataset.promoteId }),
      });
      historyStatus.textContent = tr("Saved to your ledger. The raw PDF still expires on schedule.", "已沉淀到长期台账，原始 PDF 仍会按计划自动删除。");
      await loadAccount();
    } catch (error) {
      promote.disabled = false;
      historyStatus.textContent = error.message;
    }
    return;
  }
  if (!remove) return;
  if (!window.confirm(tr("Delete this recent document and its encrypted PDF now?", "现在删除这份最近单据及其加密 PDF 吗？"))) return;
  historyStatus.textContent = tr("Deleting recent history…", "正在删除最近历史……");
  try {
    await request(`/api/v1/documents/${encodeURIComponent(remove.dataset.deleteHistory)}`, { method: "DELETE" });
    historyStatus.textContent = tr("Recent document deleted.", "最近单据已删除。");
    await loadAccount();
  } catch (error) { historyStatus.textContent = error.message; }
});

document.querySelector("#ledgerList").addEventListener("click", async (event) => {
  const remove = event.target.closest("[data-delete-ledger]");
  if (!remove) return;
  if (!window.confirm(tr("Delete this saved ledger entry?", "删除这条长期台账记录吗？"))) return;
  ledgerStatus.textContent = tr("Deleting ledger entry…", "正在删除台账记录……");
  try {
    await request(`/api/v1/ledger/${encodeURIComponent(remove.dataset.deleteLedger)}`, { method: "DELETE" });
    ledgerStatus.textContent = tr("Ledger entry deleted.", "台账记录已删除。");
    await loadAccount();
  } catch (error) { ledgerStatus.textContent = error.message; }
});

document.querySelector("#diagnosticCaseList").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-case]");
  if (!button) return;
  if (!window.confirm(tr("Delete this encrypted diagnostic case now? This cannot be undone.", "立即删除该加密诊断案例？此操作无法撤销。"))) return;
  diagnosticCaseStatus.textContent = tr("Deleting diagnostic evidence…", "正在删除诊断证据…");
  try {
    await request(`/api/v1/diagnostic-cases/${encodeURIComponent(button.dataset.deleteCase)}`, { method: "DELETE" });
    const response = await request("/api/v1/diagnostic-cases");
    renderDiagnosticCases(await response.json());
    diagnosticCaseStatus.textContent = tr("Diagnostic evidence deleted.", "诊断证据已删除。");
  } catch (error) { diagnosticCaseStatus.textContent = error.message; }
});

document.querySelector("#cancelSubscriptionButton").addEventListener("click", async () => {
  if (!window.confirm(tr("Cancel the ReceiptSift subscription at PayPal? Your access updates after PayPal confirms cancellation.", "在 PayPal 取消 ReceiptSift 订阅？PayPal 确认后访问权限将自动更新。"))) return;
  billingStatus.textContent = tr("Sending cancellation to PayPal…", "正在向 PayPal 发送取消请求…");
  try {
    await request("/api/billing/paypal/cancel", { method: "POST" });
    billingStatus.textContent = tr("Cancellation accepted. PayPal will confirm the account update shortly.", "取消请求已接受，PayPal 将尽快确认账户更新。");
  } catch (error) { billingStatus.textContent = error.message; }
});

document.querySelector("#exportDataButton").addEventListener("click", async () => {
  exportStatus.textContent = tr("Preparing export…", "正在准备导出…");
  try {
    const response = await request("/api/v1/account/export.json");
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "receiptsift-account-export.json";
    link.click();
    URL.revokeObjectURL(link.href);
    exportStatus.textContent = tr("Account data downloaded.", "账户数据已下载。");
  } catch (error) { exportStatus.textContent = error.message; }
});

document.querySelector("#deleteAccountButton").addEventListener("click", async () => {
  const password = document.querySelector("#deletePassword").value;
  if (!password) { deleteStatus.textContent = tr("Enter your password first.", "请先输入密码。"); return; }
  if (!window.confirm(tr("Permanently delete your account, billing mapping, and aggregate usage records?", "永久删除账户、计费映射与汇总用量记录？"))) return;
  deleteStatus.textContent = tr("Deleting account…", "正在删除账户…");
  try {
    await request("/api/v1/account", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    location.replace("/?account=deleted");
  } catch (error) { deleteStatus.textContent = error.message; }
});

document.querySelector("#signOutButton").addEventListener("click", async () => {
  try { await fetch("/api/auth/logout", { method: "POST" }); } finally { location.replace("/login"); }
});

locale?.subscribe(() => { locale.apply(); loadAccount().catch((error) => { deleteStatus.textContent = error.message; }); });
loadAccount().catch((error) => { deleteStatus.textContent = error.message; });
