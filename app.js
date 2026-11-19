const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const englishCopy = {
  "ReceiptSift": "ReceiptSift", "单份解析": "Single document", "批量工作台": "Batch workspace", "套餐": "Pricing", "账户": "Account", "帮助": "Help", "云端保护": "Protected cloud", "账户后台": "Account", "退出登录": "Sign out", "产品导航": "Product navigation", "账单解析产品演示": "Receipt parsing product demo", "关闭": "Close",
  "ReceiptSift PDF": "ReceiptSift PDF", "隐私": "Privacy",
  "切换语言": "Switch language", "跳到主要内容": "Skip to content", "法律信息": "Legal", "返回首页": "Back to home", "搜索": "Search",
  "PDF 账单与收据解析": "PDF bill & receipt parser", "每一张账单，": "Every receipt,", "都清楚了。": "perfectly clear.",
  "从原始凭证到可编辑表格。商家、日期、金额和商品明细，几秒钟整理完成。": "From original PDF to editable spreadsheet. Merchant, date, totals, and line items, organized in seconds.",
  "选择 PDF": "Choose PDF", "查看示例": "View live demo", "PDF 账单与收据解析 · 原文定位 · CSV 导出": "PDF bills and receipts · Source tracing · CSV export", "商家": "Merchant", "总金额": "Total", "合计": "Total", "6 项字段已提取": "6 fields extracted",
  "把 PDF 放进来。": "Drop in a PDF.", "剩下的，交给ReceiptSift。": "ReceiptSift does the rest.",
  "文字型与扫描版 PDF 会在受保护的服务中解析，并加密保留最多 7 天，方便重新核对。": "Text and scanned PDFs are parsed by the protected service and encrypted for up to 7 days so you can review them again.",
  "拖入 PDF，或点击选择": "Drop a PDF here, or choose a file", "单个文件不超过 20 MB": "Up to 20 MB per file", "选择文件": "Choose file",
  "数据有出处，核对有依据。": "Every value, traceable.", "ReceiptSift不会只给你一个答案。点击任意字段，就能看到它在原凭证中的位置。": "ReceiptSift shows its work. Select any field to locate it on the original receipt.",
  "服务费": "Service fee", "税费 / 服务费": "Tax / service fee", "74% · 请确认": "74% · Review", "原文定位": "Source tracing", "每个字段都有来源": "Every field links to its source",
  "明细识别": "Line-item extraction", "商品逐行变成表格": "Items become editable rows", "一键导出": "One-click export", "CSV 可继续编辑": "Continue working in CSV",
  "正在解析": "Parsing", "让字迹，变成数据。": "Turning print into data.", "商家名称": "Merchant name", "开具日期": "Issue date", "解析完成": "Complete",
  "你的账单，": "Your receipt", "已经整理好。": "is ready.", "正在整理提取摘要。": "Preparing the extraction summary.", "1 页 · 识别完成": "1 page · Extraction complete",
  "原始凭证。": "Original receipt.", "7 天内可重新核对。": "Available to review for 7 days.", "点击下方提取字段，凭证中的对应位置会立即高亮。": "Select an extracted field below to highlight its source on the receipt.",
  "上传凭证第一页预览": "First-page preview of uploaded receipt", "核对提取结果": "Review extracted data", "黑色描边表示这项数据需要你看一眼。": "An outlined field needs a quick review.",
  "可信度": "Confidence", "基本信息": "Key fields", "商品明细": "Line items", "币种": "Currency", "CNY 人民币": "CNY Chinese yuan", "USD 美元": "USD US dollar",
  "EUR 欧元": "EUR Euro", "GBP 英镑": "GBP Pound sterling", "JPY 日元": "JPY Japanese yen", "收据编号": "Receipt no.", "商品小计": "Subtotal", "小费": "Tip",
  "请对照原文确认税费或附加费用。": "Confirm tax or additional charges against the source.", "支付方式": "Payment method", "金额核对一致": "Totals match", "小计 + 税费 + 小费 = 总金额": "Subtotal + tax + tip = total",
  "＋ 添加一项": "+ Add item", "项目": "Item", "数量": "Qty", "金额": "Amount",
  "本张凭证总金额": "Receipt total", "解析另一份": "Parse another", "撤销修改": "Reset changes", "应用修改": "Apply changes", "导出 CSV": "Export CSV",
  "条款": "Terms", "数据处理": "Data handling", "Cookie 政策": "Cookie Policy", "退款政策": "Refund Policy", "联系邮箱": "Contact", "© 2026 ReceiptSift · 受保护的私测版": "© 2026 ReceiptSift · Protected private beta", "把收据变成结构化数据，同时保留每一项来源。": "Structured receipt data with every source kept in view.",
  "受保护的解析服务": "Protected parsing service",
  "我知道了": "Got it", "识别页面文字": "Reading page text", "寻找金额与日期": "Finding totals and dates", "整理商品明细": "Structuring line items", "检查金额是否一致": "Reconciling totals",
  "请选择有效的 PDF 文件。": "Please choose a valid PDF file.", "请选择 PDF 文件": "Please choose a PDF file", "这里只接收 PDF 文件": "Only PDF files are accepted here",
  "项目名称": "Item name", "删除": "Delete", "新项目": "New item", "已添加一条商品明细": "Line item added", "已删除该商品明细": "Line item removed",
  "已恢复为初始识别结果": "Original extracted data restored", "修改已应用，仅保留在当前页面": "Changes applied for this page only", "修改已保存到最近7天历史": "Changes saved to your 7-day history", "CSV 已生成并开始下载": "CSV generated and download started",
  "隐私说明": "Privacy", "怎样使用ReceiptSift？": "How do I use ReceiptSift?", "使用条款": "Terms of use",
  "选择 PDF 或打开真实示例。解析完成后可核对来源、在当前页面编辑字段并导出 CSV。扫描件会使用服务端 OCR。": "Choose a PDF or open the live sample. Then review sources, edit fields on this page, and export CSV. Scans use server-side OCR.",
  "本工具用于辅助整理单据，不构成会计、财务或税务建议。请在正式使用数据前人工复核。": "This tool assists with document organization and is not accounting, financial, or tax advice. Review data before official use.",
  "服务未连接": "Service offline", "后端服务未连接，请使用 run.ps1 启动完整应用。": "The backend is offline. Start the complete app with run.ps1.",
  "文件不能超过 20 MB": "The file cannot exceed 20 MB", "解析失败": "Parsing failed", "网络请求失败": "Network request failed",
  "金额需要核对": "Totals need review", "未找到可核对的金额": "Not enough totals to reconcile",
  "当前页面临时结果": "Temporary result on this page", "ReceiptSift 不保存凭证、预览或提取内容。离开前请先导出 CSV。": "ReceiptSift does not save your receipt, preview, or extracted content. Export CSV before leaving.",
  "最近7天加密历史": "Encrypted 7-day history", "PDF、预览、提取结果和修改会加密保留7天，可从账户页重新打开或提前删除。": "PDFs, previews, extracted results, and edits are encrypted for 7 days. Reopen or delete them sooner from your account.",
  "单份和批量单据的原始 PDF、预览、提取结果与修改会加密保留最多7天，也可以随时提前删除。确认沉淀到台账时只长期保存结构化字段和行项目，不复制原始 PDF。主动提交的诊断材料最多加密保存14天。": "Source PDFs, previews, extracted results, and edits for single and batch documents are encrypted for up to 7 days and can be deleted sooner. Confirming a ledger entry keeps only structured fields and line items, not the raw PDF. Submitted diagnostic evidence is encrypted for up to 14 days.",
  "选择 PDF 或打开真实示例。解析完成后可核对来源、编辑字段并保存。最近7天可以从账户页重新打开，也可以确认沉淀到长期台账。": "Choose a PDF or open the live sample. Review sources, edit fields, and save. Reopen it from your account for 7 days or confirm it into the long-term ledger.",
  "离开当前结果吗？未应用的修改会丢失，但最近解析结果仍会加密保留7天。": "Leave this result? Unapplied edits will be lost, but the recent result remains encrypted for 7 days.",
  "订单编号将在解析后生成": "Order ID will appear after parsing", "报告结果有误": "Report incorrect result", "自愿诊断报告": "Optional diagnostic report",
  "帮助我们复盘错误结果": "Help us investigate an incorrect result", "仅当你主动提交时，我们才会加密保存本次原始结果、当前修改和问题描述，最长保留 14 天。上传的 PDF 也会一并加密保存。": "Only when you submit this report, we encrypt and retain the original result, current edits, and your description for up to 14 days. Your uploaded PDF is included.",
  "哪里不对？": "What is incorrect?", "请说明错误字段或你期望的正确结果。": "Name the incorrect field or the result you expected.",
  "我同意为排查此问题而保存上述诊断材料，最长 14 天。我可以在账户页提前删除。": "I agree to retain this diagnostic evidence for up to 14 days to investigate this issue. I can delete it sooner from my account.",
  "取消": "Cancel", "加密提交报告": "Submit encrypted report",
  "选择核对方式": "Choose a review layout", "需要逐项检查时，使用并排比对。": "Use side-by-side compare when checking fields one by one.", "核对布局": "Review layout", "标准模式": "Standard view", "并排比对": "Compare side by side"
};

const additionalAppCopy = {
  hi: {
    "单份解析": "एक दस्तावेज़", "批量工作台": "बैच कार्यक्षेत्र", "账户": "खाता", "帮助": "सहायता", "云端保护": "सुरक्षित क्लाउड", "退出登录": "साइन आउट",
    "PDF 账单与收据解析": "PDF बिल और रसीद पार्सर", "每一张账单，": "हर रसीद,", "都清楚了。": "पूरी तरह स्पष्ट।",
    "从原始凭证到可编辑表格。商家、日期、金额和商品明细，几秒钟整理完成。": "मूल PDF से संपादन योग्य तालिका तक। विक्रेता, तारीख, कुल और मदें कुछ ही सेकंड में व्यवस्थित।",
    "选择 PDF": "PDF चुनें", "查看示例": "लाइव डेमो देखें", "把 PDF 放进来。": "PDF यहाँ डालें।", "剩下的，交给ReceiptSift。": "बाकी ReceiptSift संभालेगा।",
    "拖入 PDF，或点击选择": "PDF यहाँ छोड़ें या फ़ाइल चुनें", "单个文件不超过 20 MB": "प्रति फ़ाइल अधिकतम 20 MB", "选择文件": "फ़ाइल चुनें",
    "数据有出处，核对有依据。": "हर मान का स्रोत उपलब्ध।", "正在解析": "पार्स हो रहा है", "让字迹，变成数据。": "दस्तावेज़ को डेटा में बदल रहे हैं।",
    "商家名称": "विक्रेता", "开具日期": "जारी करने की तारीख", "总金额": "कुल राशि", "解析完成": "पूरा हुआ", "核对提取结果": "निकाले गए डेटा की समीक्षा करें",
    "基本信息": "मुख्य फ़ील्ड", "商品明细": "पंक्ति मदें", "币种": "मुद्रा", "收据编号": "रसीद संख्या", "商品小计": "उप-योग", "小费": "टिप", "支付方式": "भुगतान विधि",
    "解析另一份": "दूसरा पार्स करें", "撤销修改": "बदलाव रीसेट करें", "应用修改": "बदलाव लागू करें", "导出 CSV": "CSV निर्यात करें", "报告结果有误": "गलत परिणाम रिपोर्ट करें"
  },
  es: {
    "单份解析": "Documento individual", "批量工作台": "Espacio por lotes", "账户": "Cuenta", "帮助": "Ayuda", "云端保护": "Nube protegida", "退出登录": "Cerrar sesión",
    "PDF 账单与收据解析": "Analizador de facturas y recibos PDF", "每一张账单，": "Cada recibo,", "都清楚了。": "totalmente claro.",
    "从原始凭证到可编辑表格。商家、日期、金额和商品明细，几秒钟整理完成。": "Del PDF original a una tabla editable. Comercio, fecha, totales y artículos, organizados en segundos.",
    "选择 PDF": "Elegir PDF", "查看示例": "Ver demo", "把 PDF 放进来。": "Suelta un PDF.", "剩下的，交给ReceiptSift。": "ReceiptSift hace el resto.",
    "拖入 PDF，或点击选择": "Suelta un PDF aquí o elige un archivo", "单个文件不超过 20 MB": "Hasta 20 MB por archivo", "选择文件": "Elegir archivo",
    "数据有出处，核对有依据。": "Cada dato, con su fuente.", "正在解析": "Analizando", "让字迹，变成数据。": "Convirtiendo el documento en datos.",
    "商家名称": "Comercio", "开具日期": "Fecha de emisión", "总金额": "Total", "解析完成": "Completado", "核对提取结果": "Revisar datos extraídos",
    "基本信息": "Campos principales", "商品明细": "Artículos", "币种": "Moneda", "收据编号": "N.º de recibo", "商品小计": "Subtotal", "小费": "Propina", "支付方式": "Método de pago",
    "解析另一份": "Analizar otro", "撤销修改": "Restablecer cambios", "应用修改": "Aplicar cambios", "导出 CSV": "Exportar CSV", "报告结果有误": "Informar resultado incorrecto"
  },
  ar: {
    "单份解析": "مستند واحد", "批量工作台": "مساحة الدُفعات", "账户": "الحساب", "帮助": "المساعدة", "云端保护": "سحابة محمية", "退出登录": "تسجيل الخروج",
    "PDF 账单与收据解析": "محلل فواتير وإيصالات PDF", "每一张账单，": "كل إيصال،", "都清楚了。": "واضح تمامًا.",
    "从原始凭证到可编辑表格。商家、日期、金额和商品明细，几秒钟整理完成。": "من ملف PDF الأصلي إلى جدول قابل للتعديل. التاجر والتاريخ والإجماليات والبنود مرتبة خلال ثوانٍ.",
    "选择 PDF": "اختر PDF", "查看示例": "عرض نموذج", "把 PDF 放进来。": "أفلت ملف PDF.", "剩下的，交给ReceiptSift。": "ودع الباقي لـ ReceiptSift.",
    "拖入 PDF，或点击选择": "أفلت ملف PDF هنا أو اختر ملفًا", "单个文件不超过 20 MB": "حتى 20 MB لكل ملف", "选择文件": "اختر ملفًا",
    "数据有出处，核对有依据。": "لكل قيمة مصدرها.", "正在解析": "جارٍ التحليل", "让字迹，变成数据。": "نحوّل المستند إلى بيانات.",
    "商家名称": "التاجر", "开具日期": "تاريخ الإصدار", "总金额": "الإجمالي", "解析完成": "اكتمل", "核对提取结果": "راجع البيانات المستخرجة",
    "基本信息": "الحقول الأساسية", "商品明细": "البنود", "币种": "العملة", "收据编号": "رقم الإيصال", "商品小计": "المجموع الفرعي", "小费": "الإكرامية", "支付方式": "طريقة الدفع",
    "解析另一份": "تحليل مستند آخر", "撤销修改": "إعادة ضبط التغييرات", "应用修改": "تطبيق التغييرات", "导出 CSV": "تصدير CSV", "报告结果有误": "الإبلاغ عن نتيجة خاطئة"
  }
};

const currencySymbols = { CNY: "¥", USD: "$", EUR: "€", GBP: "£", JPY: "¥" };
const fieldUi = {
  merchant: { input: "#merchant", confidence: "#merchantConfidence" },
  date: { input: "#date", confidence: "#dateConfidence" },
  currency: { input: "#currency", confidence: "#currencyConfidence" },
  receipt_number: { input: "#receiptNumber", confidence: "#receiptNumberConfidence" },
  subtotal: { input: "#subtotal", confidence: "#subtotalConfidence" },
  tax: { input: "#tax", confidence: "#taxConfidence" },
  tip: { input: "#tip", confidence: "#tipConfidence" },
  total: { input: "#total", confidence: "#totalConfidence" },
  payment_method: { input: "#payment", confidence: "#paymentConfidence" },
};
const dynamicFieldsByType = {
  receipt: ["card_last4", "gross_amount", "discount", "refund"],
  invoice: ["bill_to_name", "bill_to_address", "ship_to_name", "ship_to_address", "original_invoice_number", "due_date", "account_number", "purchase_order_number", "payment_terms", "gross_amount", "discount", "shipping", "fees", "amount_paid", "balance_due"],
  bill: ["due_date", "account_number", "service_period_start", "service_period_end", "previous_balance", "payments", "credits", "current_charges", "adjustments", "fees", "late_fee", "minimum_due", "autopay_date"]
};
const numericDocumentFields = new Set(["gross_amount", "discount", "refund", "subtotal", "shipping", "fees", "tax", "tip", "total", "amount_paid", "balance_due", "previous_balance", "payments", "credits", "current_charges", "adjustments", "late_fee", "minimum_due"]);
const dynamicFieldLabels = {
  card_last4: ["Card last 4", "卡号后四位"], gross_amount: ["Gross amount", "原始金额"], discount: ["Discount", "折扣"], refund: ["Refund", "退款"],
  customer_name: ["Customer / bill to", "客户 / 付款方"], bill_to_name: ["Bill to", "账单接收方"], bill_to_address: ["Bill-to address", "账单地址"], ship_to_name: ["Ship to", "收货方"], ship_to_address: ["Ship-to address", "收货地址"], original_invoice_number: ["Original invoice", "原发票编号"], due_date: ["Due date", "到期日"], account_number: ["Account number", "账户编号"], purchase_order_number: ["Purchase order", "采购订单号"], payment_terms: ["Payment terms", "付款条款"],
  shipping: ["Shipping", "运费"], fees: ["Fees", "其他费用"], amount_paid: ["Amount paid", "已支付"], balance_due: ["Balance due", "未付余额"],
  service_period_start: ["Service period start", "服务期开始"], service_period_end: ["Service period end", "服务期结束"], previous_balance: ["Previous balance", "上期余额"], payments: ["Payments", "付款"], credits: ["Credits", "抵扣"], current_charges: ["Current charges", "本期费用"], adjustments: ["Adjustments", "调整"], late_fee: ["Late fee", "滞纳金"], minimum_due: ["Minimum due", "最低应付"], autopay_date: ["Autopay date", "自动扣款日"]
};
const dynamicFieldNames = new Set(Object.values(dynamicFieldsByType).flat());
const requiredFieldsByType = {
  receipt: new Set(["merchant", "date", "currency", "total"]),
  invoice: new Set(["merchant", "date", "currency", "receipt_number", "total"]),
  bill: new Set(["merchant", "currency", "total", "due_date", "account_number"])
};

let language = window.ReceiptSiftLocale?.get() || "en";
let currentDocument = null;
let initialDocument = null;
let currentSourceFile = null;
let diagnosticAvailable = false;
let diagnosticSubmitted = false;
let items = [];
let toastTimer;
let progressTimer;
let selectedSourceField = null;
let reviewMode = "flow";
let modalReturnFocus = null;
let activeUploadErrorKey = "";
const textRecords = [];
const attributeRecords = [];

function t(source) {
  if (language === "zh") return source;
  if (language === "en") return englishCopy[source] || source;
  return additionalAppCopy[language]?.[source] || englishCopy[source] || source;
}
const apiErrorCopy = {
  authentication_required: ["Sign in to continue.", "请先登录后继续。"],
  rate_limit_reached: ["Too many attempts. Try again later.", "操作过于频繁，请稍后再试。"],
  file_too_large: ["The PDF exceeds the upload limit.", "PDF 超过上传大小限制。"],
  not_pdf: ["Only valid PDF files are accepted.", "仅支持有效的 PDF 文件。"],
  monthly_limit_reached: ["The monthly processing limit has been reached.", "本月处理额度已用完。"],
  plan_page_limit_exceeded: ["This PDF exceeds the page limit for the current plan.", "这份 PDF 超出当前套餐的页数限制。"],
  ai_daily_budget_reached: ["Today's AI processing budget has been reached. Try again later.", "今天的 AI 处理预算已达到上限，请稍后再试。"],
  atlas_unavailable: ["The extraction service is temporarily unavailable.", "解析服务暂时不可用，请稍后再试。"],
  diagnostic_consent_required: ["Confirm consent before submitting.", "提交前请先确认授权。"],
  diagnostic_reporting_unavailable: ["Secure diagnostic reporting is not configured.", "安全诊断报告尚未配置。"],
  parse_order_not_found: ["The parse order could not be found.", "未找到这次解析记录。"]
};
function apiErrorMessage(code, serverMessage, fallback) {
  const localized = apiErrorCopy[String(code || "")];
  if (localized) return window.ReceiptSiftLocale?.t(localized[0], localized[1]) || localized[0];
  if (language !== "zh") return serverMessage || fallback || "The request failed. Please try again.";
  return code ? `请求失败（${code}），请稍后重试。` : "请求失败，请稍后重试。";
}
function clone(value) { return JSON.parse(JSON.stringify(value)); }
function fieldValue(name) { return currentDocument?.fields?.[name]?.value ?? null; }
function translatedText(value) {
  const match = value.match(/^(\s*)(.*?)(\s*)$/s);
  if (!match) return value;
  const [, before, content, after] = match;
  return `${before}${t(content)}${after}`;
}

function captureTranslatableContent() {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    if (!node.nodeValue.trim() || ["SCRIPT", "STYLE"].includes(node.parentElement?.tagName)) continue;
    textRecords.push({ node, source: node.nodeValue });
  }
  $$('[aria-label]').forEach((element) => attributeRecords.push({ element, attribute: "aria-label", source: element.getAttribute("aria-label") }));
}

function applyLanguage(nextLanguage) {
  language = nextLanguage;
  const activeLocale = window.ReceiptSiftLocale?.locales?.[language];
  document.documentElement.lang = activeLocale?.htmlLang || "en";
  document.documentElement.dir = activeLocale?.dir || "ltr";
  document.title = language === "zh" ? "ReceiptSift PDF｜账单与收据解析" : "ReceiptSift PDF | Bill & receipt parser";
  textRecords.forEach(({ node, source }) => { if (node.isConnected) node.nodeValue = translatedText(source); });
  attributeRecords.forEach(({ element, attribute, source }) => { if (element.isConnected) element.setAttribute(attribute, t(source)); });
  $("#languageToggle").value = language;
  $("#languageToggle").setAttribute("aria-label", window.ReceiptSiftLocale?.t("Choose language", "选择语言") || "Choose language");
  if (activeUploadErrorKey) $("#uploadError").textContent = t(activeUploadErrorKey);
  if (currentDocument) renderDocument(currentDocument, false);
  window.ReceiptSiftLocale?.updateLinks();
}

function setView(view) {
  ["uploadView", "processingView", "reviewView"].forEach((id) => document.getElementById(id).classList.toggle("hidden", id !== view));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setReviewMode(nextMode, moveToWorkspace = true) {
  reviewMode = nextMode === "compare" ? "compare" : "flow";
  const workspace = $("#reviewWorkspace");
  workspace.dataset.reviewMode = reviewMode;
  workspace.classList.toggle("compare-mode", reviewMode === "compare");
  $$('[data-review-mode]').forEach((button) => {
    const active = button.dataset.reviewMode === reviewMode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  if (moveToWorkspace) workspace.scrollIntoView({ behavior: "smooth", block: "start" });
  if (reviewMode !== "compare" || !currentDocument) return;
  const fieldName = selectedSourceField || Object.keys(fieldUi).find((name) => currentDocument.fields?.[name]?.source?.bbox);
  if (fieldName) requestAnimationFrame(() => requestAnimationFrame(() => highlightSource(fieldName)));
}

function showToast(messageKey) {
  clearTimeout(toastTimer);
  $("#toast p").textContent = t(messageKey);
  $("#toast").classList.add("show");
  toastTimer = setTimeout(() => $("#toast").classList.remove("show"), 3200);
}

function showToastText(message) {
  clearTimeout(toastTimer);
  $("#toast p").textContent = message;
  $("#toast").classList.add("show");
  toastTimer = setTimeout(() => $("#toast").classList.remove("show"), 3200);
}

function openModal(titleKey, textKey) {
  modalReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  $("#modalTitle").textContent = t(titleKey);
  $("#modalText").textContent = t(textKey);
  $("#modalBackdrop").classList.remove("hidden");
  $("#modalClose").focus();
}
function closeModal() {
  const wasOpen = !$("#modalBackdrop").classList.contains("hidden");
  $("#modalBackdrop").classList.add("hidden");
  if (wasOpen && modalReturnFocus?.isConnected) modalReturnFocus.focus();
  modalReturnFocus = null;
}
function setUploadError(messageKey = "") {
  activeUploadErrorKey = messageKey;
  $("#uploadError").classList.toggle("hidden", !messageKey);
  if (messageKey) $("#uploadError").textContent = t(messageKey);
}

async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, options); }
  catch (_) { throw new Error(t("后端服务未连接，请使用 run.ps1 启动完整应用。")); }
  if (response.status === 401) {
    location.replace(`/login?next=${encodeURIComponent(location.pathname)}`);
    throw new Error(apiErrorMessage("authentication_required"));
  }
  if (!response.ok) {
    let payload = {};
    try { payload = await response.json(); } catch (_) { /* non-JSON error */ }
    throw new Error(apiErrorMessage(payload.error?.code, payload.error?.message, `${response.status} ${response.statusText}`));
  }
  if (response.status === 204) return null;
  return response.json();
}

function beginProgress(filename) {
  clearInterval(progressTimer);
  $("#processingFilename").textContent = filename;
  setView("processingView");
  let percent = 8;
  const update = () => {
    percent = Math.min(92, percent + Math.max(1, Math.round((94 - percent) * .12)));
    const step = percent < 35 ? "识别页面文字" : percent < 60 ? "寻找金额与日期" : percent < 82 ? "整理商品明细" : "检查金额是否一致";
    $("#progressBar").style.transform = `scaleX(${percent / 100})`;
    $("#processingPercent").textContent = `${percent}%`;
    $("#processingStep").textContent = t(step);
  };
  update();
  progressTimer = setInterval(update, 280);
}

async function completeProgress() {
  clearInterval(progressTimer);
  $("#progressBar").style.transform = "scaleX(1)";
  $("#processingPercent").textContent = "100%";
  $("#processingStep").textContent = t("检查金额是否一致");
  await new Promise((resolve) => setTimeout(resolve, 260));
}

async function parseFile(file) {
  if (!file.name.toLowerCase().endsWith(".pdf") || (file.type && file.type !== "application/pdf")) {
    setUploadError("请选择有效的 PDF 文件。");
    return showToast("这里只接收 PDF 文件");
  }
  if (file.size > 20 * 1024 * 1024) {
    setUploadError("文件不能超过 20 MB");
    return showToast("文件不能超过 20 MB");
  }
  setUploadError();
  beginProgress(file.name);
  const body = new FormData();
  body.append("file", file, file.name);
  try {
    const documentResult = await api("/api/v1/documents", { method: "POST", body });
    await completeProgress();
    currentSourceFile = file;
    diagnosticSubmitted = false;
    renderDocument(documentResult, true);
    setView("reviewView");
  } catch (error) {
    clearInterval(progressTimer);
    setView("uploadView");
    setUploadError(error.message || "解析失败");
    showToastText(error.message || t("解析失败"));
  } finally { $("#fileInput").value = ""; }
}

async function parseSample() {
  setUploadError();
  beginProgress("cedar-and-finch-sample.pdf");
  $("#sampleButton").disabled = true;
  try {
    const documentResult = await api("/api/v1/documents/sample", { method: "POST" });
    await completeProgress();
    currentSourceFile = null;
    diagnosticSubmitted = false;
    renderDocument(documentResult, true);
    setView("reviewView");
  } catch (error) {
    clearInterval(progressTimer);
    setView("uploadView");
    setUploadError(error.message || "解析失败");
    showToastText(error.message || t("解析失败"));
  } finally { $("#sampleButton").disabled = false; }
}

function numberInputValue(value) { return value == null ? "" : Number(value).toFixed(2); }
function formatConfidence(value) { return value > 0 ? `${Math.round(value * 100)}%${value < .85 ? ` · ${language !== "zh" ? "Review" : "请确认"}` : ""}` : "…"; }
function formatMoney(value, currency = "USD") {
  if (value == null || Number.isNaN(Number(value))) return "…";
  try { return new Intl.NumberFormat(window.ReceiptSiftLocale?.locales?.[language]?.htmlLang || "en-US", { style: "currency", currency }).format(Number(value)); }
  catch (_) { return `${currencySymbols[currency] || ""}${Number(value).toFixed(2)}`; }
}

function renderField(name) {
  const metadata = currentDocument.fields?.[name] || { value: null, confidence: 0, source: null };
  const config = fieldUi[name];
  const input = $(config.input);
  if (name === "currency") {
    const currency = metadata.value || "USD";
    if (![...input.options].some((option) => option.value === currency)) input.add(new Option(currency, currency));
    input.value = currency;
  } else if (config.numeric || numericDocumentFields.has(name)) input.value = numberInputValue(metadata.value);
  else input.value = metadata.value ?? "";
  $(config.confidence).textContent = formatConfidence(metadata.confidence || 0);
  const card = input.closest(".field-card");
  const verifierFlagged = (currentDocument.verification?.discrepancies || []).some((issue) => String(issue.field || "").split(/[.[]/, 1)[0] === name);
  const missing = metadata.value == null || metadata.value === "";
  const required = (requiredFieldsByType[currentDocument.document_type] || requiredFieldsByType.receipt).has(name);
  card.classList.toggle("needs-review", (required && missing) || (!missing && (metadata.confidence || 0) < .85) || verifierFlagged);
  card.classList.toggle("is-missing", missing);
}

function renderDynamicFields() {
  dynamicFieldNames.forEach((name) => { delete fieldUi[name]; });
  const documentType = currentDocument?.document_type || "receipt";
  const names = dynamicFieldsByType[documentType] || dynamicFieldsByType.receipt;
  const container = $("#specialFields");
  container.innerHTML = names.map((name) => {
    const [en, zh] = dynamicFieldLabels[name] || [name, name];
    const label = language !== "zh" ? en : zh;
    const inputType = numericDocumentFields.has(name) ? 'type="number" step="0.01"' : 'type="text"';
    return `<label class="field-card ${["customer_name", "payment_terms"].includes(name) ? "wide" : ""}" data-field="${name}"><span>${label} <i id="dynamic-${name}-confidence">…</i></span><input id="dynamic-${name}" ${inputType} /></label>`;
  }).join("");
  names.forEach((name) => {
    fieldUi[name] = { input: `#dynamic-${name}`, confidence: `#dynamic-${name}-confidence`, numeric: numericDocumentFields.has(name) };
  });
  container.classList.toggle("hidden", names.length === 0);
}

function renderDocument(documentResult, rememberInitial = false) {
  currentDocument = documentResult;
  $("#reportButton").disabled = !diagnosticAvailable || diagnosticSubmitted;
  if (rememberInitial) initialDocument = clone(documentResult);
  items = (documentResult.items || []).map((item) => ({ ...item }));
  $("#reviewFilename").textContent = documentResult.filename;
  const method = documentResult.extraction_method === "atlas_text_markitdown"
    ? "MarkItDown + AI text"
    : documentResult.extraction_method?.startsWith("atlas_qwen3_vl")
    ? "Atlas AI vision"
    : documentResult.extraction_method === "ocr"
      ? "OCR"
      : documentResult.extraction_method === "mixed"
        ? "OCR + PDF text"
        : documentResult.extraction_method?.endsWith("_atlas_fallback")
          ? "Local fallback"
          : "PDF text";
  const typeLabel = ({ receipt: ["Receipt", "收据"], invoice: ["Invoice", "发票"], bill: ["Bill", "账单"] }[documentResult.document_type] || ["Document", "单据"])[language !== "zh" ? 0 : 1];
  $("#reviewFileMeta").textContent = language !== "zh" ? `${typeLabel} · ${documentResult.page_count} ${documentResult.page_count === 1 ? "page" : "pages"} · ${method}` : `${typeLabel} · ${documentResult.page_count} 页 · ${method}`;
  const orderId = documentResult.order_id || documentResult.id;
  $("#reviewOrderMeta").textContent = language !== "zh" ? `Order ${orderId.slice(0, 12)}` : `订单 ${orderId.slice(0, 12)}`;
  renderDynamicFields();
  const filledCount = Object.keys(fieldUi).filter((name) => documentResult.fields?.[name]?.value !== null && documentResult.fields?.[name]?.value !== "" && documentResult.fields?.[name]?.value !== undefined).length;
  const reviewCount = (documentResult.warnings || []).length;
  const needsReview = documentResult.status === "needs_review";
  $("#reviewKicker").textContent = language !== "zh" ? (needsReview ? "Review needed" : "Complete") : (needsReview ? "需要确认" : "解析完成");
  $("#reviewTitle").textContent = language !== "zh" ? (needsReview ? "Check this receipt before export." : "Your receipt is ready.") : (needsReview ? "导出前，请核对这张账单。" : "你的账单已经整理好。");
  $("#reviewSummary").textContent = language !== "zh"
    ? `${filledCount} key fields and ${items.length} line items extracted. ${reviewCount} ${reviewCount === 1 ? "item needs" : "items need"} review.`
    : `共提取 ${filledCount} 项基本信息与 ${items.length} 项商品明细。${reviewCount} 项需要确认。`;
  $("#confidenceScore").textContent = Math.round((documentResult.overall_confidence || 0) * 100) || "…";
  Object.keys(fieldUi).forEach(renderField);
  updateCurrencyDisplay();
  renderItems();
  renderReconciliation();
  renderVerification();
  renderPreview();
  $(".tabs [data-tab='basic'] span").textContent = filledCount;
  $(".tabs [data-tab='items'] span").textContent = items.length;
}

function renderVerification() {
  const notice = $("#verificationNotice");
  const verification = currentDocument.verification;
  if (!verification || verification.status !== "completed") {
    notice.classList.add("hidden");
    return;
  }
  const verdict = verification.verdict || "review";
  const fields = [...new Set((verification.discrepancies || []).map((issue) => String(issue.field || "").split(/[.[]/, 1)[0]).filter(Boolean))].slice(0, 4);
  notice.classList.toggle("verification-pass", verdict === "pass");
  notice.classList.remove("hidden");
  if (verdict === "pass") {
    $("#verificationTitle").textContent = language !== "zh" ? "Independent check completed" : "独立复核已完成";
    $("#verificationText").textContent = language !== "zh"
      ? "No conflicting value was found. Any outlined missing fields still need your review."
      : "未发现冲突值；仍请核对带描边的缺失字段。";
    return;
  }
  $("#verificationTitle").textContent = language !== "zh" ? "Independent check found a difference" : "独立复核发现差异";
  const fieldText = fields.length ? fields.join(", ") : (language !== "zh" ? "the extracted data" : "提取数据");
  $("#verificationText").textContent = language !== "zh"
    ? `Review ${fieldText} against the receipt before exporting. GPT suggestions were not applied automatically.`
    : `导出前请对照原凭证核对 ${fieldText}。GPT 建议未自动覆盖当前结果。`;
}

function renderPreview() {
  selectedSourceField = null;
  $("#sourceOverlay").classList.add("hidden");
  const image = $("#previewImage");
  const text = $("#previewText");
  if (currentDocument.preview_data_url) {
    text.classList.add("hidden"); image.classList.remove("hidden");
    image.src = currentDocument.preview_data_url;
    image.onload = () => { if (selectedSourceField) highlightSource(selectedSourceField); };
  } else {
    image.classList.add("hidden"); text.classList.remove("hidden");
    text.textContent = (currentDocument.pages || []).map((page) => page.text).join("\n\n");
  }
}

function highlightSource(fieldName) {
  selectedSourceField = fieldName;
  $$(".field-card").forEach((card) => card.classList.toggle("active", card.dataset.field === fieldName));
  const source = currentDocument?.fields?.[fieldName]?.source;
  const overlay = $("#sourceOverlay");
  const image = $("#previewImage");
  if (source?.page !== 1) {
    overlay.classList.add("hidden");
    return showToastText(language !== "zh" ? `Source is on page ${source?.page}; only page 1 is previewed.` : `原文位于第 ${source?.page} 页；当前只预览第 1 页。`);
  }
  if (!source?.bbox) {
    overlay.classList.add("hidden");
    return showToastText(language !== "zh" ? `AI evidence is on page ${source?.page || 1}; a precise region is not available.` : `AI 证据位于第 ${source?.page || 1} 页；暂无精确坐标。`);
  }
  if (image.classList.contains("hidden") || !image.clientWidth) return overlay.classList.add("hidden");
  const [x0, y0, x1, y1] = source.bbox;
  overlay.style.left = `${image.offsetLeft + x0 * image.clientWidth}px`;
  overlay.style.top = `${image.offsetTop + y0 * image.clientHeight}px`;
  overlay.style.width = `${Math.max(4, (x1 - x0) * image.clientWidth)}px`;
  overlay.style.height = `${Math.max(4, (y1 - y0) * image.clientHeight)}px`;
  overlay.classList.remove("hidden");
  const preview = $("#documentPreview");
  if (reviewMode === "compare") {
    const targetTop = overlay.offsetTop - preview.clientHeight / 2 + overlay.offsetHeight / 2;
    preview.scrollTo({ top: Math.max(0, targetTop), behavior: "smooth" });
  } else {
    preview.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function makeInput(label, value, key, index, type = "text") {
  const input = document.createElement("input");
  input.setAttribute("aria-label", label); input.value = value ?? ""; input.dataset.key = key; input.dataset.index = index; input.type = type;
  if (type === "number" && key === "quantity") input.min = "0";
  if (key === "amount" || key === "unit_price") input.step = "0.01";
  return input;
}

function renderItems() {
  const container = $("#itemRows"); container.innerHTML = "";
  items.forEach((item, index) => {
    const row = document.createElement("div"); row.className = "table-row";
    row.appendChild(makeInput(t("项目名称"), item.description, "description", index));
    row.appendChild(makeInput(t("数量"), item.quantity, "quantity", index, "number"));
    row.appendChild(makeInput(t("金额"), Number(item.amount || 0).toFixed(2), "amount", index, "number"));
    const button = document.createElement("button"); button.setAttribute("aria-label", `${t("删除")} ${item.description}`); button.dataset.delete = index; button.textContent = "×";
    row.appendChild(button); container.appendChild(row);
  });
  $(".items-summary span").textContent = language !== "zh" ? `${items.length} line items extracted` : `共识别 ${items.length} 项商品`;
  $(".tabs [data-tab='items'] span").textContent = items.length;
  updateSubtotalDisplay();
}

function updateSubtotalDisplay() {
  const subtotal = items.reduce((sum, item) => sum + Number(item.amount || 0), 0);
  $("#itemsSubtotal").textContent = formatMoney(subtotal, $("#currency").value);
}
function updateCurrencyDisplay() {
  const currency = $("#currency").value || "USD";
  $$(".currency-symbol").forEach((element) => { element.textContent = currencySymbols[currency] || currency; });
  $("#stickyTotal").textContent = formatMoney(Number($("#total").value), currency);
  updateSubtotalDisplay();
}

function renderReconciliation() {
  const reconciliation = currentDocument.reconciliation || {};
  const primaryCheck = (currentDocument.reconciliations || []).find((entry) => entry.matched != null) || (currentDocument.reconciliations || [])[0];
  const matched = reconciliation.matched;
  $("#reconcileCard").classList.toggle("mismatch", matched === false);
  $("#reconcileIcon").textContent = matched === false ? "!" : matched === true ? "✓" : "?";
  $("#reconcileTitle").textContent = t(matched === false ? "金额需要核对" : matched === true ? "金额核对一致" : "未找到可核对的金额");
  const subtotal = fieldValue("subtotal"), tax = fieldValue("tax"), tip = fieldValue("tip"), total = fieldValue("total");
  $("#reconcileText").textContent = currentDocument.document_type === "receipt" && subtotal != null && total != null
    ? `${formatMoney(subtotal, fieldValue("currency"))} + ${formatMoney(tax || 0, fieldValue("currency"))} + ${formatMoney(tip || 0, fieldValue("currency"))} = ${formatMoney(total, fieldValue("currency"))}`
    : (primaryCheck?.formula || t("小计 + 税费 + 小费 = 总金额"));
}

function collectPatch() {
  const numeric = (selector) => $(selector).value.trim() === "" ? null : Number($(selector).value);
  const merchant = $("#merchant").value.trim() || null;
  const issueDate = $("#date").value.trim() || null;
  const documentNumber = $("#receiptNumber").value.trim() || null;
  const patch = {
    document_type: currentDocument?.document_type || "receipt", document_subtype: currentDocument?.document_subtype || null,
    merchant, vendor_name: merchant, date: issueDate, issue_date: issueDate, currency: $("#currency").value,
    receipt_number: documentNumber, document_number: documentNumber, subtotal: numeric("#subtotal"), tax: numeric("#tax"), tip: numeric("#tip"), total: numeric("#total"),
    payment_method: $("#payment").value.trim() || null,
    items: items.map((item) => ({ ...item, description: item.description || t("新项目"), quantity: Number(item.quantity || 0), unit_price: item.unit_price == null ? null : Number(item.unit_price), amount: Number(item.amount || 0) })),
  };
  (dynamicFieldsByType[patch.document_type] || []).forEach((name) => {
    const input = $(fieldUi[name]?.input);
    if (!input) return;
    patch[name] = numericDocumentFields.has(name) ? (input.value.trim() === "" ? null : Number(input.value)) : (input.value.trim() || null);
  });
  return patch;
}

function recalculateClientReconciliation() {
  const value = (name) => currentDocument.fields?.[name]?.value;
  const check = (code, formula, actual, expected) => {
    const difference = actual == null || expected == null ? null : Number((Number(actual) - Number(expected)).toFixed(2));
    return { code, formula, matched: difference == null ? null : Math.abs(difference) <= .02, difference };
  };
  const type = currentDocument.document_type || "receipt";
  let checks;
  if (type === "invoice") {
    const subtotal = value("subtotal");
    const expected = subtotal == null ? null : Number(subtotal) - Number(value("discount") || 0) + Number(value("shipping") || 0) + Number(value("fees") || 0) + Number(value("tax") || 0);
    checks = [check("invoice_total", "subtotal - discount + shipping + fees + tax = total", value("total"), expected)];
    if (value("balance_due") != null && value("amount_paid") != null && value("total") != null) checks.push(check("invoice_balance", "total - amount_paid = balance_due", value("balance_due"), Number(value("total")) - Number(value("amount_paid"))));
  } else if (type === "bill") {
    const hasComponents = value("previous_balance") != null || value("current_charges") != null;
    const expected = hasComponents ? Number(value("previous_balance") || 0) - Number(value("payments") || 0) - Number(value("credits") || 0) + Number(value("current_charges") || 0) + Number(value("adjustments") || 0) + Number(value("fees") || 0) + Number(value("late_fee") || 0) + Number(value("tax") || 0) : null;
    checks = [check("bill_balance", "previous balance - payments - credits + current charges + adjustments + fees + late fee + tax = amount due", value("balance_due") ?? value("total"), expected)];
  } else {
    const subtotal = value("subtotal");
    checks = [check("receipt_total", "subtotal + tax + tip = total", value("total"), subtotal == null ? null : Number(subtotal) + Number(value("tax") || 0) + Number(value("tip") || 0))];
  }
  currentDocument.reconciliations = checks;
  const primary = checks.find((entry) => entry.matched != null) || checks[0];
  currentDocument.reconciliation = { matched: primary.matched, difference: primary.difference };
}

function applyChanges(notify = true) {
  if (!currentDocument) return null;
  const patch = collectPatch();
  Object.entries(patch).forEach(([name, value]) => {
    if (name === "items") return;
    if (name === "document_type" || name === "document_subtype") { currentDocument[name] = value; return; }
    const previous = currentDocument.fields?.[name] || {};
    currentDocument.fields[name] = { value, confidence: 1, source: previous.source || null, corrected: true };
  });
  currentDocument.items = patch.items.map((item) => ({ ...item, confidence: 1, source: null, corrected: true }));
  const subtotal = patch.subtotal ?? (patch.items.length ? Number(patch.items.reduce((sum, item) => sum + item.amount, 0).toFixed(2)) : null);
  if (patch.subtotal == null && subtotal != null) currentDocument.fields.subtotal = { value: subtotal, confidence: 1, source: null, corrected: true };
  recalculateClientReconciliation();
  const resolvedCodes = new Set();
  if (patch.merchant) resolvedCodes.add("merchant_missing");
  if (patch.total != null) resolvedCodes.add("total_missing");
  if (patch.items.length) resolvedCodes.add("items_missing");
  if (currentDocument.reconciliation.matched) ["totals_mismatch", "invoice_total_mismatch", "invoice_balance_mismatch", "bill_balance_mismatch"].forEach((code) => resolvedCodes.add(code));
  currentDocument.warnings = (currentDocument.warnings || []).filter((warning) => !resolvedCodes.has(warning.code));
  if (currentDocument.reconciliation.matched === false && !currentDocument.warnings.some((warning) => /mismatch$/.test(warning.code))) currentDocument.warnings.push({ code: `${currentDocument.document_type || "receipt"}_total_mismatch`, message: "Amounts do not reconcile." });
  currentDocument.status = !currentDocument.warnings.length && currentDocument.reconciliation.matched !== false ? "ready" : "needs_review";
  currentDocument.updated_at = new Date().toISOString();
  renderDocument(currentDocument, false);
  if (notify) showToast("修改已应用，仅保留在当前页面");
  return currentDocument;
}

async function loadRequestedHistory() {
  const documentId = new URLSearchParams(location.search).get("history");
  if (!documentId) return;
  try {
    const documentResult = await api(`/api/v1/documents/${encodeURIComponent(documentId)}`);
    originalFile = null;
    diagnosticSubmitted = false;
    renderDocument(documentResult, true);
    setView("reviewView");
  } catch (error) {
    setUploadError(error.message || t("解析失败"));
    showToastText(error.message || t("解析失败"));
  }
}

async function persistChanges() {
  if (!currentDocument) return;
  const patch = collectPatch();
  applyChanges(false);
  if (currentDocument.storage_mode !== "recent_7d") {
    showToast("修改已应用，仅保留在当前页面");
    return;
  }
  const saved = await api(`/api/v1/documents/${encodeURIComponent(currentDocument.id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  renderDocument(saved, true);
  showToast("修改已保存到最近7天历史");
}

function csvCell(value) {
  let text = value == null ? "" : String(value);
  if (typeof value === "string" && /^[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

function exportCsv() {
  if (!currentDocument) return;
  $("#exportButton").disabled = true;
  try {
    applyChanges(false);
    const fields = currentDocument.fields || {};
    const value = (name) => fields[name]?.value ?? "";
    const rows = currentDocument.items?.length ? currentDocument.items : [{ description: "", quantity: "", unit_price: "", amount: "" }];
    const header = ["document_type", "document_number", "vendor_name", "issue_date", "due_date", "currency", "description", "sku", "quantity", "unit", "unit_price", "discount", "tax_rate", "tax_amount", "amount"];
    const csvRows = [header, ...rows.map((item) => [currentDocument.document_type || "receipt", value("document_number"), value("vendor_name"), value("issue_date"), value("due_date"), value("currency"), item.description, item.sku, item.quantity, item.unit, item.unit_price, item.discount, item.tax_rate, item.tax_amount, item.amount])];
    const blob = new Blob(["\ufeff", csvRows.map((row) => row.map(csvCell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a"); link.href = URL.createObjectURL(blob);
    const stem = (currentDocument.filename || "receipt").replace(/\.pdf$/i, "").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "receipt";
    link.download = `${stem}.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 0);
    fetch("/api/v1/account/usage/csv-export", { method: "POST", keepalive: true }).catch(() => {});
    showToast("CSV 已生成并开始下载");
  } catch (error) { showToastText(error.message || t("解析失败")); }
  finally { $("#exportButton").disabled = false; }
}

function exportJson() {
  if (!currentDocument) return;
  applyChanges(false);
  const fieldNames = ["vendor_name", "vendor_address", "vendor_tax_id", "customer_name", "customer_address", "bill_to_name", "bill_to_address", "ship_to_name", "ship_to_address", "document_number", "original_invoice_number", "issue_date", "due_date", "currency", "account_number", "purchase_order_number", "payment_terms", "card_last4", "payment_method", "gross_amount", "discount", "refund", "subtotal", "shipping", "fees", "tax", "tip", "total", "amount_paid", "balance_due", "previous_balance", "payments", "credits", "adjustments", "current_charges", "late_fee", "minimum_due", "service_period_start", "service_period_end", "autopay_date"];
  const payload = {
    schema_version: currentDocument.schema_version || "1.0",
    document_type: currentDocument.document_type || "receipt",
    document_subtype: currentDocument.document_subtype || null,
    filename: currentDocument.filename,
    status: currentDocument.status,
    fields: Object.fromEntries(fieldNames.map((name) => [name, currentDocument.fields?.[name]?.value ?? null])),
    line_items: (currentDocument.items || []).map((item) => Object.fromEntries(["description", "sku", "quantity", "unit", "unit_price", "discount", "tax_rate", "tax_amount", "amount"].map((name) => [name, item[name] ?? null]))),
    reconciliations: currentDocument.reconciliations || []
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" });
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob);
  const stem = (currentDocument.filename || "document").replace(/\.pdf$/i, "").replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "document";
  link.download = `${stem}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 0);
  showToastText(language !== "zh" ? "JSON generated and download started" : "JSON 已生成并开始下载");
}

function resetData() { if (initialDocument) { renderDocument(clone(initialDocument), false); showToast("已恢复为初始识别结果"); } }

function discardCurrentResult() {
  currentDocument = null;
  initialDocument = null;
  currentSourceFile = null;
  diagnosticSubmitted = false;
  items = [];
  selectedSourceField = null;
  $("#previewImage").removeAttribute("src");
}

function confirmDiscardCurrent() {
  if (!currentDocument) return true;
  if (!window.confirm(t("离开当前结果吗？未应用的修改会丢失，但最近解析结果仍会加密保留7天。"))) return false;
  discardCurrentResult();
  return true;
}

function diagnosticResult(documentResult) {
  const payload = clone(documentResult);
  ["id", "order_id", "filename", "created_at", "updated_at", "preview_url", "preview_data_url", "storage_mode"]
    .forEach((key) => delete payload[key]);
  return payload;
}

function openDiagnosticDialog() {
  if (!currentDocument) return;
  if (!diagnosticAvailable) {
    return showToastText(language !== "zh" ? "Secure diagnostic reporting is not configured." : "安全诊断报告尚未配置。");
  }
  $("#diagnosticDescription").value = "";
  $("#diagnosticConsent").checked = false;
  $("#diagnosticStatus").textContent = "";
  $("#diagnosticIntro").textContent = currentSourceFile
    ? (language !== "zh"
      ? "Only when you submit this report, we encrypt and retain the original result, current edits, your description, and this PDF for up to 14 days."
      : "仅当你主动提交时，我们才会加密保存本次原始结果、当前修改、问题描述和这份 PDF，最长保留 14 天。")
    : (language !== "zh"
      ? "This live demo has no uploaded PDF. If submitted, we encrypt and retain the original result, current edits, and your description for up to 14 days."
      : "真实示例没有用户上传的 PDF。提交后，我们会加密保存原始结果、当前修改和问题描述，最长保留 14 天。");
  $("#diagnosticDialog").showModal();
  $("#diagnosticDescription").focus();
}

function closeDiagnosticDialog() {
  if ($("#diagnosticDialog").open) $("#diagnosticDialog").close();
}

async function submitDiagnosticReport(event) {
  event.preventDefault();
  if (!currentDocument || !initialDocument) return;
  if (!$("#diagnosticConsent").checked) {
    $("#diagnosticStatus").textContent = language !== "zh" ? "Confirm consent before submitting." : "提交前请先确认授权。";
    return;
  }
  applyChanges(false);
  const submitButton = $("#diagnosticSubmit");
  submitButton.disabled = true;
  $("#diagnosticStatus").textContent = language !== "zh" ? "Encrypting and submitting…" : "正在加密并提交…";
  const body = new FormData();
  body.append("order_id", currentDocument.order_id || currentDocument.id);
  body.append("description", $("#diagnosticDescription").value.trim());
  body.append("consent", "true");
  body.append("original_result_json", JSON.stringify(diagnosticResult(initialDocument)));
  body.append("corrected_result_json", JSON.stringify(diagnosticResult(currentDocument)));
  if (currentSourceFile) body.append("file", currentSourceFile, currentSourceFile.name);
  try {
    const payload = await api("/api/v1/diagnostic-cases", { method: "POST", body });
    closeDiagnosticDialog();
    diagnosticSubmitted = true;
    $("#reportButton").disabled = true;
    const shortId = payload.case.case_id.slice(0, 12);
    showToastText(language !== "zh" ? `Diagnostic case ${shortId} submitted.` : `诊断案例 ${shortId} 已提交。`);
  } catch (error) {
    $("#diagnosticStatus").textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function checkRuntime() {
  try {
    const health = await api("/api/health");
    diagnosticAvailable = Boolean(health.diagnostic_reporting_available);
    $("#reportButton").disabled = !diagnosticAvailable || diagnosticSubmitted;
    $("#reportButton").title = diagnosticAvailable ? "" : (language !== "zh" ? "Secure reporting is not configured." : "安全诊断报告尚未配置。");
    $("#runtimeStatus").textContent = language !== "zh" ? (health.ocr_available ? "Protected + OCR" : "Protected service") : (health.ocr_available ? "受保护 + OCR" : "受保护服务");
    $("#runtimeStatus").classList.remove("runtime-offline");
  } catch (_) { diagnosticAvailable = false; $("#reportButton").disabled = true; $("#runtimeStatus").textContent = t("服务未连接"); $("#runtimeStatus").classList.add("runtime-offline"); }
}

$("#sampleButton").addEventListener("click", parseSample);
$("#fileInput").addEventListener("change", (event) => { const [file] = event.target.files; if (file) parseFile(file); });
const dropZone = $("#dropZone");
["dragenter", "dragover"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.add("dragging"); }));
["dragleave", "drop"].forEach((name) => dropZone.addEventListener(name, (event) => { event.preventDefault(); dropZone.classList.remove("dragging"); }));
dropZone.addEventListener("drop", (event) => { const [file] = event.dataTransfer.files; if (file) parseFile(file); });

const openPrivacy = () => openModal("隐私说明", "单份和批量单据的原始 PDF、预览、提取结果与修改会加密保留最多7天，也可以随时提前删除。确认沉淀到台账时只长期保存结构化字段和行项目，不复制原始 PDF。主动提交的诊断材料最多加密保存14天。");
const returnToUpload = () => { if (confirmDiscardCurrent()) setView("uploadView"); };
$("#homeButton").addEventListener("click", returnToUpload); $("#navOverview").addEventListener("click", returnToUpload);
window.ReceiptSiftLocale?.bindButton($("#languageToggle"));
window.ReceiptSiftLocale?.subscribe((next) => { applyLanguage(next); checkRuntime(); });
$$('[data-review-mode]').forEach((button) => button.addEventListener("click", () => setReviewMode(button.dataset.reviewMode)));
$("#newFileButton").addEventListener("click", returnToUpload); $("#resetButton").addEventListener("click", resetData);
$("#saveButton").addEventListener("click", () => persistChanges().catch((error) => showToastText(error.message || t("解析失败")))); $("#exportButton").addEventListener("click", exportCsv); $("#exportJsonButton").addEventListener("click", exportJson);
$("#reportButton").addEventListener("click", openDiagnosticDialog);
$("#diagnosticForm").addEventListener("submit", submitDiagnosticReport);
$("#diagnosticClose").addEventListener("click", closeDiagnosticDialog); $("#diagnosticCancel").addEventListener("click", closeDiagnosticDialog);
$("#footerPrivacy").addEventListener("click", openPrivacy); $("#footerData").addEventListener("click", openPrivacy);
$("#footerTerms").addEventListener("click", () => openModal("使用条款", "本工具用于辅助整理单据，不构成会计、财务或税务建议。请在正式使用数据前人工复核。"));
$("#logoutButton").addEventListener("click", async () => {
  if (!confirmDiscardCurrent()) return;
  try { await fetch("/api/auth/logout", { method: "POST" }); } finally { location.replace("/login"); }
});
$("#accountButton").addEventListener("click", () => { if (confirmDiscardCurrent()) location.href = "/account"; });
$("#pricingButton").addEventListener("click", () => { if (confirmDiscardCurrent()) location.href = "/pricing"; });
$("#modalClose").addEventListener("click", closeModal); $("#modalConfirm").addEventListener("click", closeModal); $("#modalBackdrop").addEventListener("click", (event) => { if (event.target === $("#modalBackdrop")) closeModal(); });

$$(".tabs button").forEach((tab) => tab.addEventListener("click", () => {
  $$(".tabs button").forEach((button) => button.classList.remove("active")); tab.classList.add("active");
  const basic = tab.dataset.tab === "basic"; $("#basicPanel").classList.toggle("hidden", !basic); $("#itemsPanel").classList.toggle("hidden", basic);
}));
$(".field-grid").addEventListener("click", (event) => { const card = event.target.closest(".field-card"); if (card && currentDocument) highlightSource(card.dataset.field); });
$("#specialFields").addEventListener("click", (event) => { const card = event.target.closest(".field-card"); if (card && currentDocument) highlightSource(card.dataset.field); });
$("#currency").addEventListener("change", updateCurrencyDisplay); $("#total").addEventListener("input", updateCurrencyDisplay);
$("#addItemButton").addEventListener("click", () => { items.push({ description: t("新项目"), quantity: 1, unit_price: null, amount: 0 }); renderItems(); showToast("已添加一条商品明细"); });
$("#itemRows").addEventListener("input", (event) => { const input = event.target.closest("input"); if (!input) return; const key = input.dataset.key; items[Number(input.dataset.index)][key] = key === "description" ? input.value : Number(input.value); updateSubtotalDisplay(); });
$("#itemRows").addEventListener("click", (event) => { const button = event.target.closest("[data-delete]"); if (!button) return; items.splice(Number(button.dataset.delete), 1); renderItems(); showToast("已删除该商品明细"); });
window.addEventListener("resize", () => { if (selectedSourceField) highlightSource(selectedSourceField); });
window.addEventListener("beforeunload", (event) => { if (!currentDocument || currentDocument.storage_mode === "recent_7d") return; event.preventDefault(); event.returnValue = ""; });
document.addEventListener("click", (event) => {
  const link = event.target.closest("a[href]");
  if (!link || !currentDocument || link.target === "_blank" || link.hasAttribute("download")) return;
  if (!confirmDiscardCurrent()) event.preventDefault();
}, true);
document.addEventListener("keydown", (event) => { if (event.key === "Escape") { closeModal(); closeDiagnosticDialog(); } });

captureTranslatableContent();
applyLanguage(language);
checkRuntime();
loadRequestedHistory();
