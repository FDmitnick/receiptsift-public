const $ = (selector) => document.querySelector(selector);

const copy = {
  zh: {
    skip: "跳到工作台", single: "单份解析", batch: "批量工作台", pricing: "价格", account: "账户", help: "帮助", library: "批次资料库", batches: "批次",
    batchName: "批次名称", cancel: "取消", create: "创建", loadingBatches: "正在加载批次...", retention: "保留期",
    retentionText: "原始 PDF：7 天<br />提取结果：7 天", startTitle: "建立一个财务单据批次。", startText: "创建批次后，一次加入最多 100 份 PDF 收据、发票或账单。网页关闭后后台仍可继续处理。",
    createBatch: "创建批次", activeBatch: "当前批次", exportCsv: "下载汇总表", exportItems: "商品明细 CSV", exportTax: "交给会计的 Excel", exportJson: "JSON 数据", moreExports: "更多导出", deleteBatch: "删除批次", progress: "处理进度",
    dropTitle: "添加 PDF 财务单据", dropText: "拖入多个文件，或点击选择。每份 PDF 不超过 20 MB。", documents: "文件明细", filter: "筛选", all: "全部",
    review: "待审核", failed: "失败", ready: "已完成", reviewQueue: "异常审核", reviewEmpty: "需要注意的文件会出现在这里。选择任意一行即可查看或修正。",
    selectedReceipt: "已选单据", openSource: "打开已保留的原 PDF", retry: "重试处理", saveReview: "保存审核", emptyBatches: "还没有批次。",
    emptyDocs: "这个批次还没有 PDF。", files: "份文件", staged: "待确认", queued: "等待", processing: "处理中", uploaded: "已加入", duplicates: "重复文件",
    startProcessing: "开始处理", deleteDocument: "删除", processingLocked: "处理中", uploadFailed: "上传失败", saved: "审核已保存", retryQueued: "已重新排队", deleteConfirm: "删除这个批次及其所有加密 PDF 和结果？",
    status: "状态", pages: "页数", total: "总额", noResult: "尚无可编辑的提取结果。", documentLedger: "文件明细",
    sourcePreview: "原单据定位", loadingPreview: "正在加载原单据页面...", taxDisclaimer: "用于记账与报税准备，不用于直接向 IRS 申报。", selectVisible: "选择当前可删除项",
    previousIssue: "上一个异常", nextIssue: "下一个异常", saveNext: "保存并继续", backToBatch: "返回批次"
  },
  hi: {
    skip: "कार्यस्थान पर जाएँ", single: "एक दस्तावेज़", batch: "बैच कार्यक्षेत्र", pricing: "मूल्य", account: "खाता", help: "सहायता", library: "बैच लाइब्रेरी", batches: "बैच",
    batchName: "बैच का नाम", cancel: "रद्द करें", create: "बनाएँ", loadingBatches: "बैच लोड हो रहे हैं...", retention: "डेटा रखने की अवधि",
    retentionText: "मूल PDF: 30 दिन<br />निकाले गए परिणाम: 90 दिन", startTitle: "वित्तीय दस्तावेज़ों का बैच बनाएँ।", startText: "बैच बनाने के बाद एक बार में अधिकतम 100 PDF रसीदें, चालान या बिल जोड़ें। विंडो बंद होने पर भी प्रसंस्करण जारी रह सकता है।",
    createBatch: "बैच बनाएँ", activeBatch: "सक्रिय बैच", exportCsv: "सारांश डाउनलोड करें", exportItems: "पंक्ति-मद CSV", exportTax: "अकाउंटेंट Excel", exportJson: "JSON डेटा", moreExports: "अधिक निर्यात", deleteBatch: "बैच हटाएँ", progress: "प्रगति",
    dropTitle: "PDF वित्तीय दस्तावेज़ जोड़ें", dropText: "कई फ़ाइलें यहाँ छोड़ें या चुनें। प्रति PDF अधिकतम 20 MB।", documents: "दस्तावेज़", filter: "फ़िल्टर", all: "सभी",
    review: "समीक्षा", failed: "विफल", ready: "तैयार", reviewQueue: "अपवाद समीक्षा", reviewEmpty: "ध्यान देने वाले दस्तावेज़ यहाँ दिखेंगे। जाँच या सुधार के लिए कोई पंक्ति चुनें।",
    selectedReceipt: "चुना गया दस्तावेज़", openSource: "सहेजा गया मूल PDF खोलें", retry: "फिर प्रसंस्करण करें", saveReview: "समीक्षा सहेजें", emptyBatches: "अभी कोई बैच नहीं।",
    emptyDocs: "इस बैच में अभी कोई PDF नहीं है।", files: "फ़ाइलें", staged: "पुष्टि बाकी", queued: "कतार में", processing: "प्रसंस्करण", uploaded: "जोड़ा गया", duplicates: "डुप्लिकेट",
    startProcessing: "प्रसंस्करण शुरू करें", deleteDocument: "हटाएँ", processingLocked: "प्रसंस्करण जारी", uploadFailed: "अपलोड विफल", saved: "समीक्षा सहेजी गई", retryQueued: "फिर कतार में जोड़ा गया", deleteConfirm: "यह बैच, इसके सभी एन्क्रिप्टेड PDF और परिणाम हटाएँ?",
    status: "स्थिति", pages: "पृष्ठ", total: "कुल", noResult: "अभी कोई संपादन योग्य परिणाम नहीं।", documentLedger: "दस्तावेज़ विवरण", sourcePreview: "मूल दस्तावेज़", loadingPreview: "मूल पृष्ठ लोड हो रहे हैं...",
    taxDisclaimer: "लेखा और कर तैयारी के लिए; सीधे IRS दाख़िल करने के लिए नहीं।", selectVisible: "दिख रहे हटाने योग्य दस्तावेज़ चुनें", previousIssue: "पिछली समस्या", nextIssue: "अगली समस्या", saveNext: "सहेजें और आगे बढ़ें", backToBatch: "बैच पर वापस जाएँ"
  },
  es: {
    skip: "Ir al espacio de trabajo", single: "Documento individual", batch: "Espacio por lotes", pricing: "Precios", account: "Cuenta", help: "Ayuda", library: "Biblioteca de lotes", batches: "Lotes",
    batchName: "Nombre del lote", cancel: "Cancelar", create: "Crear", loadingBatches: "Cargando lotes...", retention: "Conservación",
    retentionText: "PDF originales: 30 días<br />Resultados extraídos: 90 días", startTitle: "Crea un lote de documentos financieros.", startText: "Después de crear el lote, añade hasta 100 recibos, facturas o cuentas PDF a la vez. El procesamiento puede continuar al cerrar la ventana.",
    createBatch: "Crear lote", activeBatch: "Lote activo", exportCsv: "Descargar resumen", exportItems: "CSV de artículos", exportTax: "Excel para el contable", exportJson: "Datos JSON", moreExports: "Más exportaciones", deleteBatch: "Eliminar lote", progress: "Progreso",
    dropTitle: "Añade documentos financieros PDF", dropText: "Suelta varios archivos o selecciónalos. Hasta 20 MB por PDF.", documents: "Documentos", filter: "Filtrar", all: "Todos",
    review: "Revisar", failed: "Fallidos", ready: "Listos", reviewQueue: "Revisión de excepciones", reviewEmpty: "Los documentos que requieran atención aparecerán aquí. Selecciona una fila para revisar o corregir.",
    selectedReceipt: "DOCUMENTO SELECCIONADO", openSource: "Abrir PDF original conservado", retry: "Reintentar procesamiento", saveReview: "Guardar revisión", emptyBatches: "Todavía no hay lotes.",
    emptyDocs: "Este lote aún no contiene PDF.", files: "archivos", staged: "Por confirmar", queued: "En cola", processing: "Procesando", uploaded: "Añadido", duplicates: "Duplicados",
    startProcessing: "Iniciar procesamiento", deleteDocument: "Eliminar", processingLocked: "Procesando", uploadFailed: "Error de carga", saved: "Revisión guardada", retryQueued: "Añadido de nuevo a la cola", deleteConfirm: "¿Eliminar este lote y todos sus PDF cifrados y resultados?",
    status: "Estado", pages: "Páginas", total: "Total", noResult: "Aún no hay resultados editables.", documentLedger: "Detalle de documentos", sourcePreview: "Documento original", loadingPreview: "Cargando páginas originales...",
    taxDisclaimer: "Para contabilidad y preparación fiscal; no para presentar directamente al IRS.", selectVisible: "Seleccionar documentos visibles que se pueden eliminar", previousIssue: "Problema anterior", nextIssue: "Problema siguiente", saveNext: "Guardar y continuar", backToBatch: "Volver al lote"
  },
  ar: {
    skip: "انتقل إلى مساحة العمل", single: "مستند واحد", batch: "مساحة الدُفعات", pricing: "الأسعار", account: "الحساب", help: "المساعدة", library: "مكتبة الدُفعات", batches: "الدُفعات",
    batchName: "اسم الدُفعة", cancel: "إلغاء", create: "إنشاء", loadingBatches: "جارٍ تحميل الدُفعات...", retention: "مدة الاحتفاظ",
    retentionText: "ملفات PDF الأصلية: 30 يومًا<br />النتائج المستخرجة: 90 يومًا", startTitle: "أنشئ دُفعة من المستندات المالية.", startText: "بعد إنشاء الدُفعة، أضف حتى 100 إيصال أو فاتورة PDF دفعة واحدة. يستمر العمل حتى بعد إغلاق النافذة.",
    createBatch: "إنشاء دُفعة", activeBatch: "الدُفعة الحالية", exportCsv: "تنزيل الملخص", exportItems: "CSV للبنود", exportTax: "Excel للمحاسب", exportJson: "بيانات JSON", moreExports: "المزيد من التصدير", deleteBatch: "حذف الدُفعة", progress: "التقدم",
    dropTitle: "أضف مستندات مالية PDF", dropText: "أفلت عدة ملفات أو اخترها. حتى 20 MB لكل PDF.", documents: "المستندات", filter: "تصفية", all: "الكل",
    review: "للمراجعة", failed: "فشل", ready: "جاهز", reviewQueue: "مراجعة الاستثناءات", reviewEmpty: "تظهر هنا المستندات التي تحتاج إلى عناية. اختر صفًا لفحصه أو تصحيحه.",
    selectedReceipt: "المستند المحدد", openSource: "فتح ملف PDF الأصلي المحفوظ", retry: "إعادة المعالجة", saveReview: "حفظ المراجعة", emptyBatches: "لا توجد دُفعات بعد.",
    emptyDocs: "لا تحتوي هذه الدُفعة على ملفات PDF بعد.", files: "ملفات", staged: "بانتظار التأكيد", queued: "في قائمة الانتظار", processing: "جارٍ المعالجة", uploaded: "تمت الإضافة", duplicates: "مكرر",
    startProcessing: "بدء المعالجة", deleteDocument: "حذف", processingLocked: "قيد المعالجة", uploadFailed: "فشل الرفع", saved: "حُفظت المراجعة", retryQueued: "أُعيد إلى قائمة الانتظار", deleteConfirm: "هل تريد حذف هذه الدُفعة وكل ملفات PDF المشفرة والنتائج؟",
    status: "الحالة", pages: "الصفحات", total: "الإجمالي", noResult: "لا توجد نتيجة قابلة للتعديل بعد.", documentLedger: "تفاصيل المستندات", sourcePreview: "المستند الأصلي", loadingPreview: "جارٍ تحميل الصفحات الأصلية...",
    taxDisclaimer: "للمحاسبة وإعداد الضرائب، وليس للتقديم المباشر إلى IRS.", selectVisible: "تحديد المستندات الظاهرة القابلة للحذف", previousIssue: "المشكلة السابقة", nextIssue: "المشكلة التالية", saveNext: "حفظ والتالي", backToBatch: "العودة إلى الدُفعة"
  }
};

const commonFieldNames = ["vendor_name", "issue_date", "due_date", "currency", "document_number", "account_number"];
const fieldNamesByType = {
  receipt: [...commonFieldNames, "card_last4", "gross_amount", "discount", "refund", "subtotal", "tax", "tip", "total", "payment_method"],
  invoice: [...commonFieldNames, "bill_to_name", "bill_to_address", "ship_to_name", "ship_to_address", "original_invoice_number", "purchase_order_number", "payment_terms", "gross_amount", "discount", "subtotal", "shipping", "fees", "tax", "total", "amount_paid", "balance_due"],
  bill: [...commonFieldNames, "service_period_start", "service_period_end", "previous_balance", "payments", "credits", "current_charges", "adjustments", "fees", "late_fee", "tax", "total", "minimum_due", "autopay_date"]
};
const numericFields = new Set(["gross_amount", "discount", "refund", "subtotal", "shipping", "fees", "tax", "tip", "total", "amount_paid", "balance_due", "previous_balance", "payments", "credits", "adjustments", "current_charges", "late_fee", "minimum_due"]);
const fieldLabels = {
  vendor_name: ["Vendor / biller", "供应商 / 出账方"], issue_date: ["Issue date", "开具日期"], due_date: ["Due date", "到期日"], currency: ["Currency", "币种"], document_number: ["Document number", "单据编号"], account_number: ["Account number", "账户编号"],
  customer_name: ["Customer / bill to", "客户 / 付款方"], bill_to_name: ["Bill to", "账单接收方"], bill_to_address: ["Bill-to address", "账单地址"], ship_to_name: ["Ship to", "收货方"], ship_to_address: ["Ship-to address", "收货地址"], original_invoice_number: ["Original invoice", "原发票编号"], purchase_order_number: ["Purchase order", "采购订单号"], payment_terms: ["Payment terms", "付款条款"],
  card_last4: ["Card last 4", "卡号后四位"], gross_amount: ["Gross amount", "原始金额"], discount: ["Discount", "折扣"], refund: ["Refund", "退款"],
  subtotal: ["Subtotal", "小计"], shipping: ["Shipping", "运费"], fees: ["Fees", "其他费用"], tax: ["Tax", "税费"], tip: ["Tip", "小费"], total: ["Total / amount due", "总额 / 应付"], payment_method: ["Payment method", "支付方式"],
  amount_paid: ["Amount paid", "已支付"], balance_due: ["Balance due", "未付余额"], service_period_start: ["Service period start", "服务期开始"], service_period_end: ["Service period end", "服务期结束"], previous_balance: ["Previous balance", "上期余额"], payments: ["Payments", "付款"], credits: ["Credits", "抵扣"], current_charges: ["Current charges", "本期费用"], adjustments: ["Adjustments", "调整"], late_fee: ["Late fee", "滞纳金"], minimum_due: ["Minimum due", "最低应付"], autopay_date: ["Autopay date", "自动扣款日"]
};
const requiredFieldsByType = {
  receipt: new Set(["vendor_name", "issue_date", "currency", "total"]),
  invoice: new Set(["vendor_name", "document_number", "issue_date", "currency", "total"]),
  bill: new Set(["vendor_name", "currency", "total"])
};
const warningFieldMap = {
  merchant_missing: ["vendor_name"], merchant_evidence_missing: ["vendor_name"], merchant_evidence_mismatch: ["vendor_name"],
  total_missing: ["total"], total_evidence_missing: ["total"], total_evidence_mismatch: ["total"], total_may_be_tender: ["total"],
  date_format_invalid: ["issue_date"], issue_date_format_invalid: ["issue_date"], due_date_format_invalid: ["due_date"],
  service_period_start_format_invalid: ["service_period_start"], service_period_end_format_invalid: ["service_period_end"], autopay_date_format_invalid: ["autopay_date"],
  totals_mismatch: ["total"], invoice_total_mismatch: ["total"], invoice_balance_mismatch: ["balance_due"],
  items_subtotal_mismatch: ["subtotal"]
};
const progressStageLabels = {
  staged: ["Waiting for confirmation", "等待确认"], queued: ["Waiting for a worker", "等待处理"],
  security_check: ["Checking PDF safety", "正在进行 PDF 安全检查"], quota_check: ["Checking plan allowance", "正在检查套餐额度"],
  document_analysis: ["Analyzing document structure", "正在分析单据结构"], model_extraction: ["Running the extraction model", "模型正在识别单据"],
  local_extraction: ["Extracting locally", "正在本地提取"], local_fallback: ["Retrying with local extraction", "云端不可用，正在本地重试"],
  quality_check: ["Checking fields and totals", "正在校验字段与金额"], independent_verification: ["Independently verifying result", "正在进行独立结果复核"],
  finalizing: ["Finalizing result", "正在整理最终结果"], saving: ["Saving result", "正在保存结果"],
  complete: ["Processing complete", "处理完成"], failed: ["Processing failed", "处理失败"]
};

let language = window.ReceiptSiftLocale?.get() || "en";
let batches = [];
let activeBatch = null;
let selectedDocument = null;
const selectedDocumentIds = new Set();
let bulkDeletePending = false;
const requestedBatchId = new URLSearchParams(location.search).get("batch");
const requestedDocumentId = new URLSearchParams(location.search).get("document");
let requestedSelectionApplied = false;
let pollTimer = null;
let previewState = null;
const sourceRegionRequests = new Map();

function text(key) {
  const english = document.querySelector(`[data-i18n="${key}"]`)?.dataset.english || key;
  return language === "en" ? english : (copy[language]?.[key] || english);
}
function translate() {
  const activeLocale = window.ReceiptSiftLocale?.locales?.[language];
  document.documentElement.lang = activeLocale?.htmlLang || "en";
  document.documentElement.dir = activeLocale?.dir || "ltr";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    if (!node.dataset.english) node.dataset.english = node.textContent;
    node.textContent = language === "en" ? node.dataset.english : (copy[language]?.[node.dataset.i18n] || node.dataset.english);
  });
  document.querySelectorAll("[data-i18n-html]").forEach((node) => {
    if (!node.dataset.english) node.dataset.english = node.innerHTML;
    node.innerHTML = language === "en" ? node.dataset.english : (copy[language]?.[node.dataset.i18nHtml] || node.dataset.english);
  });
  $("#languageButton").value = language;
  document.querySelector(".topbar nav")?.setAttribute("aria-label", tr("Product", "产品导航"));
  $("#newBatchButton").setAttribute("aria-label", tr("New batch", "新建批次"));
  $("#closeReviewButton").setAttribute("aria-label", tr("Back to batch", "返回批次"));
  $("#sourcePreviewPages").setAttribute("aria-label", tr("Source pages", "原单据页码"));
  $("#batchName").placeholder = tr("August client receipts", "八月客户单据");
  window.ReceiptSiftLocale?.updateLinks();
  renderBatches();
  if (activeBatch) renderActiveBatch();
  if (selectedDocument) renderReview(selectedDocument);
}
function tr(en, zh) { return window.ReceiptSiftLocale?.t(en, zh) || (language === "zh" ? zh : en); }
const apiErrorCopy = {
  authentication_required: ["Sign in to continue.", "请先登录后继续。"],
  admin_required: ["Owner access is required.", "需要所有者权限。"],
  rate_limit_reached: ["Too many attempts. Try again later.", "操作过于频繁，请稍后再试。"],
  batch_not_found: ["This batch could not be found.", "未找到这个批次。"],
  document_not_found: ["This document could not be found.", "未找到这份单据。"],
  document_processing: ["A selected document is already processing. Refresh the list and try again.", "所选文件中有一份已开始处理，请刷新列表后重试。"],
  batch_plan_required: ["Batch processing requires a Plus or Pro plan.", "批量处理需要 Plus 或 Pro 套餐。"],
  batch_file_limit_exceeded: ["This batch has reached its file limit.", "这个批次已达到文件数量上限。"],
  batch_storage_not_configured: ["Batch storage is not configured.", "批处理存储尚未配置。"],
  file_too_large: ["The PDF exceeds the upload limit.", "PDF 超过上传大小限制。"],
  not_pdf: ["Only valid PDF files are accepted.", "仅支持有效的 PDF 文件。"],
  document_not_retryable: ["This document cannot be retried.", "这份单据当前无法重试。"],
  preview_unavailable: ["The source preview is unavailable.", "原单据预览暂不可用。"],
  monthly_limit_reached: ["The monthly processing limit has been reached.", "本月处理额度已用完。"],
  plan_page_limit_exceeded: ["This PDF exceeds the page limit for the current plan.", "这份 PDF 超出当前套餐的页数限制。"]
};
function apiErrorMessage(code, serverMessage, fallback) {
  const localized = apiErrorCopy[String(code || "")];
  if (localized) return tr(...localized);
  if (language !== "zh") return serverMessage || fallback || "The request failed. Please try again.";
  return code ? `请求失败（${code}），请稍后重试。` : "请求失败，请稍后重试。";
}
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[character]); }
function formatDate(value) { if (!value) return ""; return new Intl.DateTimeFormat(window.ReceiptSiftLocale?.locales?.[language]?.htmlLang || "en-US", { dateStyle: "medium" }).format(new Date(value)); }
function fieldValue(document, name) { return document?.result?.fields?.[name]?.value ?? ""; }
function addAttention(reasons, name, reason) {
  if (!name || !fieldLabels[name]) return false;
  if (!reasons[name]) reasons[name] = [];
  if (!reasons[name].includes(reason)) reasons[name].push(reason);
  return true;
}
function issueReason(code, fallback = "") {
  if (/mismatch|reconcil/.test(code)) return tr("Amounts do not reconcile", "金额对账不一致");
  if (/evidence/.test(code)) return tr("Value does not match its source evidence", "提取值与原文证据不一致");
  if (/format_invalid/.test(code)) return tr("Format looks invalid", "格式可能不正确");
  if (language === "zh") return "解析器标记了这项内容";
  return fallback || "Parser flagged this value";
}

function extractionDetail(document) {
  if (document.error_code) return tr(`Processing error (${document.error_code})`, `处理异常（${document.error_code}）`);
  const method = String(document.extraction_method || "");
  const methods = {
    ocr: ["OCR", "OCR 识别"],
    embedded_text: ["Embedded text", "可复制文本识别"],
    mixed: ["Mixed extraction", "混合识别"],
    atlas: ["Atlas extraction", "Atlas 识别"],
    markitdown: ["MarkItDown extraction", "MarkItDown 识别"],
    synthetic: ["Synthetic test", "合成测试"]
  };
  if (!method) return tr("Awaiting extraction", "等待提取");
  if (methods[method]) return tr(...methods[method]);
  if (/atlas/i.test(method)) return tr("Atlas extraction", "Atlas 识别");
  if (/markitdown/i.test(method)) return tr("MarkItDown extraction", "MarkItDown 识别");
  return language === "zh" ? "文档识别" : method.replaceAll("_", " ");
}

function validSource(field) {
  const source = field?.source;
  if (!source || !Number.isInteger(Number(source.page)) || Number(source.page) < 1) return null;
  const bbox = Array.isArray(source.bbox) && source.bbox.length === 4 ? source.bbox.map(Number) : null;
  const validBbox = bbox && bbox.every(Number.isFinite) && bbox[0] >= 0 && bbox[1] >= 0 && bbox[2] <= 1 && bbox[3] <= 1 && bbox[2] > bbox[0] && bbox[3] > bbox[1] ? bbox : null;
  return { page: Number(source.page), bbox: validBbox };
}

function previewRecords(document, attention) {
  return Object.keys(attention.reasons || {}).map((name) => {
    const source = validSource(document?.result?.fields?.[name]);
    return { name, page: source?.page || null, bbox: source?.bbox || null };
  });
}

function renderPreviewOverlays() {
  const overlays = $("#sourcePreviewOverlays");
  overlays.innerHTML = "";
  overlays.classList.toggle("has-active", Boolean(previewState?.activeField));
  if (!previewState) return;
  const pageRecords = previewState.records.filter((item) => (item.page || 1) === previewState.page);
  pageRecords.filter((item) => item.bbox).forEach((item) => {
    const [x0, y0, x1, y1] = item.bbox;
    const marker = document.createElement("div");
    marker.className = `source-highlight ${item.name === previewState.activeField ? "is-active" : ""}`;
    marker.dataset.fieldName = item.name;
    marker.style.left = `${x0 * 100}%`;
    marker.style.top = `${y0 * 100}%`;
    marker.style.width = `${(x1 - x0) * 100}%`;
    marker.style.height = `${(y1 - y0) * 100}%`;
    marker.innerHTML = `<span>${escapeHtml(fieldLabels[item.name]?.[language === "zh" ? 1 : 0] || item.name)}</span>`;
    overlays.appendChild(marker);
  });
  const noBox = pageRecords.filter((item) => !item.bbox);
  if (noBox.length) {
    const alert = document.createElement("div");
    alert.className = "source-page-alert";
    alert.textContent = tr(`${noBox.length} flagged field${noBox.length === 1 ? "" : "s"} can only be located to this page`, `${noBox.length} 个风险项只能定位到本页，无法精确框选`);
    overlays.appendChild(alert);
  }
  const boxCount = pageRecords.length - noBox.length;
  const parts = [];
  if (boxCount) parts.push(tr(`${boxCount} red source region${boxCount === 1 ? "" : "s"} on this page.`, `本页已框出 ${boxCount} 个红色原文区域。`));
  if (noBox.length) parts.push(tr("Review the matching red field on the right.", "请同时核对右侧对应的标红字段。"));
  if (boxCount) parts.push(tr("Focus a red field on the right to locate its source.", "点击右侧标红字段，可定位对应原文。"));
  $("#sourcePreviewLegend").textContent = parts.join(" ");
}

function scrollToActiveHighlight() {
  if (!previewState?.activeField) return;
  const marker = $("#sourcePreviewOverlays").querySelector(`[data-field-name="${CSS.escape(previewState.activeField)}"]`);
  const scroll = document.querySelector(".source-preview-scroll");
  if (!marker || !scroll) return;
  scroll.scrollTo({
    left: Math.max(0, marker.offsetLeft - ((scroll.clientWidth - marker.offsetWidth) / 2)),
    top: Math.max(0, marker.offsetTop - ((scroll.clientHeight - marker.offsetHeight) / 2)),
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
  });
}

function focusPreviewField(name) {
  if (!previewState) return;
  const record = previewState.records.find((item) => item.name === name);
  if (!record) return;
  previewState.activeField = name;
  if (record.page && record.page !== previewState.page) showPreviewPage(record.page);
  else {
    renderPreviewOverlays();
    scrollToActiveHighlight();
  }
}
async function loadSourceRegions(documentId) {
  if (!sourceRegionRequests.has(documentId)) {
    sourceRegionRequests.set(documentId, api(`/api/v1/batch-documents/${encodeURIComponent(documentId)}/source-regions`).catch(() => null));
  }
  const response = await sourceRegionRequests.get(documentId);
  if (!response?.fields || previewState?.document?.id !== documentId) return;
  previewState.records = previewState.records.map((item) => {
    const region = response.fields[item.name];
    return region ? { ...item, page: Number(region.page), bbox: region.bbox.map(Number) } : item;
  });
  const sourcePages = [...new Set(previewState.records.map((item) => item.page).filter(Boolean))].sort((a, b) => a - b);
  if (previewState.records.some((item) => item.page == null) && !sourcePages.includes(1)) sourcePages.unshift(1);
  previewState.pages = sourcePages.length ? sourcePages : [1];
  const activeRecord = previewState.records.find((item) => item.name === previewState.activeField && item.bbox)
    || previewState.records.find((item) => item.bbox);
  previewState.activeField = activeRecord?.name || previewState.activeField;
  showPreviewPage(activeRecord?.page || previewState.page);
}
function showPreviewPage(page) {
  if (!previewState) return;
  previewState.page = page;
  $("#sourcePreviewLoading").classList.remove("hidden", "error");
  $("#sourcePreviewLoading").textContent = tr("Loading source page...", "正在加载原单据页面...");
  $("#sourcePreviewImage").classList.remove("ready");
  $("#sourcePreviewImage").alt = tr(`Source preview, page ${page}`, `原单据预览，第 ${page} 页`);
  $("#sourcePreviewImage").src = `/api/v1/batch-documents/${encodeURIComponent(previewState.document.id)}/preview.png?page=${page}`;
  $("#sourcePreviewPages").innerHTML = previewState.pages.map((item) => `<button class="${item === page ? "active" : ""}" type="button" data-preview-page="${item}">${tr(`Page ${item}`, `第 ${item} 页`)}</button>`).join("");
  renderPreviewOverlays();
}

function renderSourcePreview(document, attention, preferredPage = null) {
  const panel = $("#sourcePreviewPanel");
  if (!document?.source_available || !document.result) {
    previewState = null;
    panel.classList.add("hidden");
    return;
  }
  const records = previewRecords(document, attention);
  const sourcePages = [...new Set(records.map((item) => item.page).filter(Boolean))].sort((a, b) => a - b);
  if (records.some((item) => item.page == null) && !sourcePages.includes(1)) sourcePages.unshift(1);
  const pages = sourcePages.length ? sourcePages : [1];
  const page = pages.includes(preferredPage) ? preferredPage : pages[0];
  const activeField = records.find((item) => item.bbox)?.name || records[0]?.name || null;
  previewState = { document, records, pages, page, activeField };
  panel.classList.remove("hidden");
  $("#sourcePreviewTitle").textContent = document.filename;
  showPreviewPage(page);
  if (records.some((item) => !item.bbox)) void loadSourceRegions(document.id);
}
function reviewAttention(document) {
  const result = document?.result || {};
  const type = result.document_type || "receipt";
  const reasons = {};
  const otherIssues = [];
  const fields = result.fields || {};
  const required = requiredFieldsByType[type] || requiredFieldsByType.receipt;

  (fieldNamesByType[type] || fieldNamesByType.receipt).forEach((name) => {
    const field = fields[name] || {};
    const value = field.value;
    if (required.has(name) && (value == null || value === "")) addAttention(reasons, name, tr("Required value was not found", "必填内容未识别"));
    if (value != null && value !== "" && Number(field.confidence) < 0.85) {
      addAttention(reasons, name, tr(`Low confidence (${Math.round(Number(field.confidence || 0) * 100)}%)`, `置信度较低（${Math.round(Number(field.confidence || 0) * 100)}%）`));
    }
  });

  if (type === "bill") {
    ["payments", "credits"].forEach((name) => {
      const value = fields[name]?.value;
      if (value != null && Number(value) < 0) addAttention(reasons, name, tr("Enter reductions as a positive amount", "扣减金额应填写为正数"));
    });
  }

  const issues = [...(result.warnings || []), ...(result.deterministic_checks || [])];
  issues.forEach((issue) => {
    const code = String(issue?.code || "");
    if (!code) return;
    let mapped = false;
    (warningFieldMap[code] || []).forEach((name) => { mapped = addAttention(reasons, name, issueReason(code, issue.message)) || mapped; });
    if (code === "bill_balance_mismatch") {
      const suspiciousReductions = ["payments", "credits"].filter((name) => Number(fields[name]?.value) < 0);
      (suspiciousReductions.length ? suspiciousReductions : ["total"]).forEach((name) => { mapped = addAttention(reasons, name, tr("Bill balance does not reconcile", "账单余额无法对平")) || mapped; });
    }
    if (!mapped && code === "items_missing") otherIssues.push(tr("Line items were not identified", "未识别出行项目"));
    else if (!mapped && code === "item_evidence_incomplete") otherIssues.push(tr("Some line items do not match source evidence", "部分行项目与原文证据不一致"));
  });

  (result.verification?.discrepancies || []).forEach((item) => {
    const name = ({ merchant: "vendor_name", date: "issue_date", receipt_number: "document_number" })[item.field] || item.field;
    if (!addAttention(reasons, name, tr("Independent verification disagreed", "独立校验结果不一致"))) otherIssues.push(tr("Independent verification found a discrepancy", "独立校验发现不一致"));
  });
  if (document.status === "needs_review" && !Object.keys(reasons).length && !otherIssues.length) otherIssues.push(tr("The parser could not isolate one field; compare the result with the source PDF", "解析器暂未定位到具体字段，请对照原 PDF 或重试"));
  return { reasons, otherIssues: [...new Set(otherIssues)] };
}
function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return "";
  const value = Math.max(0, Math.round(Number(seconds)));
  if (value < 5) return tr("under 5 sec", "不到 5 秒");
  if (value < 60) return tr(`about ${value} sec`, `约 ${value} 秒`);
  const minutes = Math.floor(value / 60); const remainder = value % 60;
  return tr(`about ${minutes}m${remainder ? ` ${remainder}s` : ""}`, `约 ${minutes} 分${remainder ? ` ${remainder} 秒` : ""}`);
}
function progressSummary(document) {
  if (document.status === "staged") return tr("Review this file, then start processing.", "请确认文件，确认后再开始处理。");
  if (document.status === "queued") {
    const position = document.queue_position ? tr(`Queue position ${document.queue_position}`, `队列第 ${document.queue_position} 位`) : tr("Waiting in queue", "正在排队");
    const estimate = document.estimated_start_seconds === null || document.estimated_start_seconds === undefined ? tr("estimating wait", "正在估算等待时间") : tr(`starts in ${formatDuration(document.estimated_start_seconds)}`, `预计 ${formatDuration(document.estimated_start_seconds)}后开始`);
    return `${position} · ${estimate}`;
  }
  if (document.status === "processing") {
    const stage = tr(...(progressStageLabels[document.progress_stage] || [document.progress_detail || "Processing", document.progress_detail || "处理中"]));
    const parts = [stage, `${document.progress_percent || 0}%`];
    if (document.elapsed_seconds !== null && document.elapsed_seconds !== undefined) parts.push(tr(`elapsed ${formatDuration(document.elapsed_seconds)}`, `已用 ${formatDuration(document.elapsed_seconds)}`));
    if (document.estimated_remaining_seconds !== null && document.estimated_remaining_seconds !== undefined) parts.push(tr(`${formatDuration(document.estimated_remaining_seconds)} remaining`, `预计剩余 ${formatDuration(document.estimated_remaining_seconds)}`));
    if (document.progress_stale) parts.push(tr("model response is slower than usual", "模型响应较慢，仍在等待"));
    return parts.join(" · ");
  }
  return "";
}
function statusLabel(status) {
  const labels = { draft: ["Draft", "草稿"], staged: ["Pending confirmation", "待确认"], queued: ["Queued", "等待"], processing: ["Processing", "处理中"], ready: ["Ready", "已完成"], needs_review: ["Needs review", "待审核"], failed: ["Failed", "失败"] };
  return tr(...(labels[status] || [status, status]));
}
async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, options); }
  catch (_) { throw new Error(tr("Unable to connect to ReceiptSift. Try again.", "无法连接 ReceiptSift，请稍后重试。")); }
  if (response.status === 401) { location.replace(`/login?next=${encodeURIComponent(location.pathname)}`); throw new Error(apiErrorMessage("authentication_required")); }
  if (!response.ok) {
    let payload = {};
    try { payload = await response.json(); } catch (_) { /* no JSON body */ }
    throw new Error(apiErrorMessage(payload.error?.code, payload.error?.message, `${response.status} ${response.statusText}`));
  }
  if (response.status === 204) return null;
  return response.json();
}
function toast(message) { $("#toast").textContent = message; $("#toast").classList.remove("hidden"); setTimeout(() => $("#toast").classList.add("hidden"), 2800); }
function showBatchForm(show = true) { $("#newBatchForm").classList.toggle("hidden", !show); if (show) { $("#batchName").value = ""; $("#batchName").focus(); } }

async function loadBatches(selectFirst = true) {
  const response = await api("/api/v1/batches");
  batches = response.batches;
  renderBatches();
  if (!activeBatch && selectFirst && batches.length) {
    const target = batches.find((batch) => batch.id === requestedBatchId) || batches[0];
    await selectBatch(target.id);
  }
}
function renderBatches() {
  if (!batches.length) { $("#batchList").innerHTML = `<p class="muted">${tr("No batches yet.", "还没有批次。")}</p>`; return; }
  $("#batchList").innerHTML = batches.map((batch) => `<button class="batch-item ${batch.id === activeBatch?.id ? "active" : ""}" data-batch-id="${batch.id}" type="button"><b>${escapeHtml(batch.name)}</b><span>${batch.document_count} ${tr("files", "份文件")} / ${statusLabel(batch.status)}</span></button>`).join("");
  document.querySelectorAll("[data-batch-id]").forEach((button) => button.addEventListener("click", () => selectBatch(button.dataset.batchId)));
}
async function selectBatch(batchId) {
  if (activeBatch?.id !== batchId) selectedDocumentIds.clear();
  activeBatch = await api(`/api/v1/batches/${batchId}`);
  const summary = { ...activeBatch }; delete summary.documents;
  const batchIndex = batches.findIndex((item) => item.id === batchId);
  if (batchIndex >= 0) batches[batchIndex] = summary; else batches.unshift(summary);
  selectedDocument = selectedDocument && activeBatch.documents.find((item) => item.id === selectedDocument.id) || null;
  reconcileBulkSelection();
  if (!requestedSelectionApplied && batchId === requestedBatchId && requestedDocumentId) {
    selectedDocument = activeBatch.documents.find((item) => item.id === requestedDocumentId) || null;
    requestedSelectionApplied = true;
  }
  reconcileBulkSelection();
  $("#emptyWorkspace").classList.add("hidden"); $("#activeWorkspace").classList.remove("hidden");
  renderBatches(); renderActiveBatch(); if (selectedDocument) renderReview(selectedDocument); else closeReview();
  schedulePolling();
}
function visibleDocuments() {
  const filter = $("#statusFilter").value;
  return (activeBatch?.documents || []).filter((item) => filter === "all" || item.status === filter);
}
function reconcileBulkSelection() {
  const deletableIds = new Set((activeBatch?.documents || []).filter((item) => item.status !== "processing").map((item) => item.id));
  [...selectedDocumentIds].forEach((id) => { if (!deletableIds.has(id)) selectedDocumentIds.delete(id); });
}
function renderBulkToolbar(documents) {
  const selectable = documents.filter((item) => item.status !== "processing");
  const lockedCount = documents.length - selectable.length;
  const selectedVisible = selectable.filter((item) => selectedDocumentIds.has(item.id)).length;
  const selectedCount = selectedDocumentIds.size;
  const selectAll = $("#selectVisibleDocuments");
  selectAll.checked = selectable.length > 0 && selectedVisible === selectable.length;
  selectAll.indeterminate = selectedVisible > 0 && selectedVisible < selectable.length;
  selectAll.disabled = bulkDeletePending || selectable.length === 0;
  $("#bulkToolbar").classList.toggle("has-selection", selectedCount > 0);
  $("#bulkToolbar").setAttribute("aria-busy", String(bulkDeletePending));
  $("#bulkSelectionSummary").textContent = [
    tr(`${selectedCount} selected`, `已选择 ${selectedCount} 份`),
    lockedCount ? tr(`${lockedCount} processing locked`, `${lockedCount} 份处理中不可删除`) : ""
  ].filter(Boolean).join(" · ");
  const deleteButton = $("#deleteSelectedButton");
  deleteButton.textContent = selectedCount
    ? tr(`Delete selected (${selectedCount})`, `删除所选（${selectedCount}）`)
    : tr("Delete selected", "删除所选");
  deleteButton.disabled = bulkDeletePending || selectedCount === 0;
}
function renderActiveBatch() {
  if (!activeBatch) { $("#emptyWorkspace").classList.remove("hidden"); $("#activeWorkspace").classList.add("hidden"); return; }
  $("#activeBatchName").textContent = activeBatch.name;
  $("#batchMeta").textContent = `${formatDate(activeBatch.created_at)} / ${activeBatch.document_count} ${tr("files", "份文件")}`;
  const completed = activeBatch.ready_count + activeBatch.review_count + activeBatch.failed_count;
  const ratio = activeBatch.document_count ? Math.round(completed / activeBatch.document_count * 100) : 0;
  $("#progressRatio").textContent = `${completed} / ${activeBatch.document_count}`;
  $("#progressBar").style.transform = `scaleX(${ratio / 100})`;
  $("#statusCounts").innerHTML = `<span>${tr("Pending confirmation", "待确认")} ${activeBatch.staged_count}</span><span>${tr("Queued", "等待")} ${activeBatch.queued_count}</span><span>${tr("Processing", "处理中")} ${activeBatch.processing_count}</span><span>${tr("Review", "待审核")} ${activeBatch.review_count}</span><span>${tr("Failed", "失败")} ${activeBatch.failed_count}</span>`;
  $("#startBatchButton").disabled = !activeBatch.staged_count;
  $("#startBatchButton").textContent = activeBatch.staged_count ? tr(`Start processing (${activeBatch.staged_count})`, `开始处理（${activeBatch.staged_count}）`) : tr("Start processing", "开始处理");
  $("#exportButton").href = `/api/v1/batches/${activeBatch.id}/export.csv`;
  $("#exportItemsButton").href = `/api/v1/batches/${activeBatch.id}/export-items.csv`;
  $("#exportTaxButton").href = `/api/v1/batches/${activeBatch.id}/export-tax-prep.xlsx`;
  $("#exportJsonButton").href = `/api/v1/batches/${activeBatch.id}/export.json?mode=clean`;
  $("#exportButton").classList.toggle("disabled", activeBatch.document_count === 0);
  $("#exportItemsButton").classList.toggle("disabled", activeBatch.document_count === 0);
  $("#exportTaxButton").classList.toggle("disabled", activeBatch.document_count === 0);
  $("#exportJsonButton").classList.toggle("disabled", activeBatch.document_count === 0);
  const exportsDisabled = activeBatch.document_count === 0;
  $("#moreExportsMenu").classList.toggle("disabled", exportsDisabled);
  $("#moreExportsMenu summary").setAttribute("aria-disabled", String(exportsDisabled));
  if (exportsDisabled) $("#moreExportsMenu").open = false;
  renderDocuments();
}
function renderDocuments() {
  reconcileBulkSelection();
  const documents = visibleDocuments();
  renderBulkToolbar(documents);
  if (!documents.length) { $("#documentTable").innerHTML = `<p class="empty-table">${tr("No documents in this view.", "当前视图中没有文件。")}</p>`; return; }
  $("#documentTable").innerHTML = documents.map((document) => {
    const total = fieldValue(document, "total"); const currency = fieldValue(document, "currency") || "";
    const processing = document.status === "processing";
    const checked = selectedDocumentIds.has(document.id);
    const detail = progressSummary(document);
    const progressBar = processing ? `<span class="document-progress" role="progressbar" aria-label="${escapeHtml(detail)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.max(0, Math.min(document.progress_percent || 0, 100))}"><i style="transform:scaleX(${Math.max(0, Math.min(document.progress_percent || 0, 100)) / 100})"></i></span>` : "";
    const selectionLabel = processing
      ? tr(`${document.filename} is processing and cannot be selected for deletion`, `${document.filename} 正在处理，不能选择删除`)
      : tr(`Select ${document.filename} for deletion`, `选择删除 ${document.filename}`);
    return `<div class="document-row ${document.id === selectedDocument?.id ? "active" : ""} ${checked ? "bulk-selected" : ""}"><label class="document-check" title="${escapeHtml(selectionLabel)}"><input data-select-document-id="${document.id}" type="checkbox" aria-label="${escapeHtml(selectionLabel)}" ${checked ? "checked" : ""} ${processing || bulkDeletePending ? "disabled" : ""} /></label><button class="document-select" data-document-id="${document.id}" type="button"><b>${escapeHtml(document.filename)}</b><span class="status ${document.status}">${statusLabel(document.status)}</span><span class="pages">${document.page_count || "?"} ${tr("pages", "页")}</span><span class="amount">${total === "" ? "" : `${escapeHtml(currency)} ${escapeHtml(total)}`}</span>${detail ? `<small class="document-progress-copy">${escapeHtml(detail)}</small>` : ""}${progressBar}</button><button class="document-delete" data-delete-document-id="${document.id}" type="button" ${processing || bulkDeletePending ? "disabled" : ""} title="${processing ? tr("Processing documents cannot be deleted yet.", "正在处理的文件暂时不能删除。") : tr("Delete document", "删除文件")}">${processing ? tr("Locked", "处理中") : tr("Delete", "删除")}</button></div>`;
  }).join("");
}
function renderReview(document) {
  const enteringReview = !$("#workspace").classList.contains("is-reviewing");
  $("#workspace").classList.add("is-reviewing");
  $("#reviewEmpty").classList.add("hidden"); $("#reviewForm").classList.remove("hidden");
  $("#reviewFilename").textContent = document.filename;
  $("#reviewState").textContent = `${statusLabel(document.status)} / ${progressSummary(document) || extractionDetail(document)}`;
  $("#sourceLink").href = `/api/v1/batch-documents/${document.id}/source.pdf`;
  $("#sourceLink").classList.toggle("hidden", !document.source_available);
  const hasResult = Boolean(document.result);
  const documentType = document.result?.document_type || "receipt";
  const fieldNames = fieldNamesByType[documentType] || fieldNamesByType.receipt;
  const attention = hasResult ? reviewAttention(document) : { reasons: {}, otherIssues: [] };
  const orderedNames = [...fieldNames].sort((left, right) => Number(Boolean(attention.reasons[right])) - Number(Boolean(attention.reasons[left])));
  $("#reviewFields").innerHTML = hasResult ? orderedNames.map((name) => {
    const reasons = attention.reasons[name] || [];
    const flagged = reasons.length > 0;
    const wide = name === "vendor_name" || name === "customer_name" || name === "payment_terms";
    return `<label class="review-field ${wide ? "wide" : ""} ${flagged ? "needs-attention" : ""}" data-field-name="${name}"><span>${fieldLabels[name][language === "zh" ? 1 : 0]}${flagged ? `<b class="field-risk-badge">${tr("CHECK", "核对")}</b>` : ""}</span><input name="${name}" ${numericFields.has(name) ? 'type="number" step="0.01"' : ""} ${flagged ? 'aria-invalid="true" aria-controls="sourcePreviewCanvas"' : ""} value="${escapeHtml(fieldValue(document, name))}" />${flagged ? `<small class="field-review-reason">${escapeHtml(reasons.join(language === "zh" ? "；" : "; "))}</small>` : ""}</label>`;
  }).join("") : `<p class="muted">${tr("No editable extraction result yet.", "尚无可编辑的提取结果。")}</p>`;
  const flaggedCount = Object.keys(attention.reasons).length;
  const attentionMessages = [flaggedCount ? tr(`Only check the ${flaggedCount} red field${flaggedCount === 1 ? "" : "s"}.`, `只需核对标红的 ${flaggedCount} 项。`) : "", ...attention.otherIssues].filter(Boolean);
  $("#reviewAttention").classList.toggle("hidden", !attentionMessages.length);
  $("#reviewAttention").textContent = attentionMessages.join(" ");
  $("#saveReviewButton").classList.toggle("hidden", !hasResult);
  $("#saveNextReviewButton").classList.toggle("hidden", !hasResult);
  $("#retryButton").classList.toggle("hidden", !["failed", "needs_review"].includes(document.status) || !document.source_available);
  updateReviewNavigation();
  renderSourcePreview(document, attention, previewState?.document?.id === document.id ? previewState.page : null);
  if (enteringReview) requestAnimationFrame(() => $("#workspace").scrollIntoView({ block: "start", behavior: "smooth" }));
}
function closeReview() {
  const previousDocumentId = selectedDocument?.id;
  selectedDocument = null;
  previewState = null;
  $("#workspace").classList.remove("is-reviewing");
  $("#reviewEmpty").classList.remove("hidden");
  $("#reviewForm").classList.add("hidden");
  $("#sourcePreviewPanel").classList.add("hidden");
  renderDocuments();
  if (previousDocumentId) requestAnimationFrame(() => {
    const row = document.querySelector(`[data-document-id="${previousDocumentId}"]`);
    row?.scrollIntoView({ block: "center", behavior: "smooth" });
    row?.focus({ preventScroll: true });
  });
}
function reviewCandidates() { return (activeBatch?.documents || []).filter((item) => item.status === "needs_review"); }
function updateReviewNavigation() {
  const queue = reviewCandidates();
  const index = queue.findIndex((item) => item.id === selectedDocument?.id);
  const inQueue = index >= 0;
  $("#reviewPosition").textContent = queue.length
    ? tr(inQueue ? `Issue ${index + 1} of ${queue.length} · Alt+↑/↓ to move` : `${queue.length} issues remain`, inQueue ? `异常 ${index + 1} / ${queue.length} · Alt+↑/↓ 切换` : `还有 ${queue.length} 份待审核`)
    : tr("No flagged documents remain.", "没有剩余待审核文件。");
  $("#previousReviewButton").disabled = !queue.length;
  $("#nextReviewButton").disabled = !queue.length;
}
function moveReview(direction) {
  const queue = reviewCandidates();
  if (!queue.length) return;
  const current = queue.findIndex((item) => item.id === selectedDocument?.id);
  const index = current < 0 ? 0 : (current + direction + queue.length) % queue.length;
  selectedDocument = queue[index];
  renderDocuments();
  renderReview(selectedDocument);
  $("#reviewPanel").scrollIntoView({ block: "start" });
}
function schedulePolling() {
  clearTimeout(pollTimer);
  if (!activeBatch || !(activeBatch.queued_count || activeBatch.processing_count)) return;
  pollTimer = setTimeout(async () => { try { await selectBatch(activeBatch.id); } catch (error) { toast(error.message); } }, 1800);
}
async function uploadFiles(files) {
  if (!activeBatch || !files.length) return;
  const form = new FormData(); [...files].forEach((file) => form.append("files", file));
  $("#uploadFeedback").classList.remove("hidden", "error"); $("#uploadFeedback").textContent = tr(`Adding ${files.length} PDFs...`, `正在加入 ${files.length} 份 PDF...`);
  try {
    const result = await api(`/api/v1/batches/${activeBatch.id}/documents`, { method: "POST", body: form });
    const duplicates = result.rejected.filter((item) => item.code === "duplicate_document").map((item) => item.filename);
    const other = result.rejected.filter((item) => item.code !== "duplicate_document");
    const parts = [tr(`${result.accepted_count} files added. Review the list, then click Start processing.`, `已加入 ${result.accepted_count} 份文件。请确认清单后点击“开始处理”。`)];
    if (duplicates.length) parts.push(tr(`Duplicates skipped: ${duplicates.join(", ")}`, `已跳过重复文件：${duplicates.join("、")}`));
    if (other.length) parts.push(tr(`Rejected: ${other.map((item) => `${item.filename} (${item.code})`).join(", ")}`, `未接受：${other.map((item) => `${item.filename} (${item.code})`).join("、")}`));
    $("#uploadFeedback").textContent = parts.join(" "); $("#uploadFeedback").classList.toggle("error", Boolean(result.rejected_count));
    await selectBatch(activeBatch.id);
  } catch (error) { $("#uploadFeedback").textContent = error.message; $("#uploadFeedback").classList.add("error"); }
  $("#fileInput").value = "";
}
async function deleteSelectedDocuments() {
  const documentIds = [...selectedDocumentIds];
  if (!activeBatch || !documentIds.length || bulkDeletePending) return;
  const confirmed = confirm(tr(
    `Permanently delete ${documentIds.length} selected document${documentIds.length === 1 ? "" : "s"}, including retained PDFs, extracted results, and review history?`,
    `永久删除所选的 ${documentIds.length} 份文件及其已保留 PDF、提取结果和审核记录？`
  ));
  if (!confirmed) return;

  const batchId = activeBatch.id;
  bulkDeletePending = true;
  renderDocuments();
  try {
    const result = await api(`/api/v1/batches/${batchId}/documents/delete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_ids: documentIds })
    });
    if (selectedDocument && documentIds.includes(selectedDocument.id)) closeReview();
    documentIds.forEach((id) => selectedDocumentIds.delete(id));
    toast(tr(
      `${result.deleted_count} document${result.deleted_count === 1 ? "" : "s"} deleted.`,
      `已删除 ${result.deleted_count} 份文件。`
    ));
    await selectBatch(batchId);
  } catch (error) {
    toast(error.message);
    try { await selectBatch(batchId); } catch (_) { /* keep the original action error visible */ }
  } finally {
    bulkDeletePending = false;
    if (activeBatch?.id === batchId) renderDocuments();
  }
}

window.ReceiptSiftLocale?.bindButton($("#languageButton"));
window.ReceiptSiftLocale?.subscribe((next) => { language = next; translate(); });
$("#newBatchButton").addEventListener("click", () => showBatchForm()); $("#emptyCreateButton").addEventListener("click", () => showBatchForm()); $("#cancelBatchButton").addEventListener("click", () => showBatchForm(false));
$("#newBatchForm").addEventListener("submit", async (event) => { event.preventDefault(); try { const batch = await api("/api/v1/batches", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: $("#batchName").value }) }); showBatchForm(false); await loadBatches(false); await selectBatch(batch.id); } catch (error) { toast(error.message); } });
$("#fileInput").addEventListener("change", (event) => uploadFiles(event.target.files));
["dragenter", "dragover"].forEach((name) => $("#dropZone").addEventListener(name, (event) => { event.preventDefault(); $("#dropZone").classList.add("dragging"); }));
["dragleave", "drop"].forEach((name) => $("#dropZone").addEventListener(name, (event) => { event.preventDefault(); $("#dropZone").classList.remove("dragging"); }));
$("#dropZone").addEventListener("drop", (event) => uploadFiles(event.dataTransfer.files));
$("#statusFilter").addEventListener("change", renderDocuments); $("#closeReviewButton").addEventListener("click", closeReview);
$("#selectVisibleDocuments").addEventListener("change", (event) => {
  visibleDocuments().filter((item) => item.status !== "processing").forEach((item) => {
    if (event.target.checked) selectedDocumentIds.add(item.id); else selectedDocumentIds.delete(item.id);
  });
  renderDocuments();
});
$("#deleteSelectedButton").addEventListener("click", deleteSelectedDocuments);
$("#previousReviewButton").addEventListener("click", () => moveReview(-1));
$("#nextReviewButton").addEventListener("click", () => moveReview(1));
$("#reviewFields").addEventListener("focusin", (event) => {
  const field = event.target.closest(".review-field.needs-attention");
  if (field) focusPreviewField(field.dataset.fieldName);
});
$("#reviewFields").addEventListener("input", (event) => {
  const field = event.target.closest(".review-field.needs-attention");
  if (!field) return;
  field.classList.remove("needs-attention"); field.classList.add("user-corrected");
  event.target.removeAttribute("aria-invalid");
  const reason = field.querySelector(".field-review-reason");
  if (reason) reason.textContent = tr("Changed. Save the review to apply.", "已修改，保存审核后生效");
  if (previewState) {
    previewState.records = previewState.records.filter((item) => item.name !== field.dataset.fieldName);
    if (previewState.activeField === field.dataset.fieldName) previewState.activeField = previewState.records.find((item) => item.bbox)?.name || null;
    renderPreviewOverlays();
  }
  const remaining = $("#reviewFields").querySelectorAll(".review-field.needs-attention").length;
  $("#reviewAttention").textContent = remaining ? tr(`Only check the ${remaining} remaining red field${remaining === 1 ? "" : "s"}.`, `还需核对标红的 ${remaining} 项。`) : tr("All flagged fields were changed. Save the review to apply.", "标红项已修改完，保存审核后生效。");
});
$("#sourcePreviewPages").addEventListener("click", (event) => {
  const button = event.target.closest("[data-preview-page]");
  if (button) showPreviewPage(Number(button.dataset.previewPage));
});
$("#sourcePreviewImage").addEventListener("load", () => {
  $("#sourcePreviewImage").classList.add("ready");
  $("#sourcePreviewLoading").classList.add("hidden");
  scrollToActiveHighlight();
});
$("#sourcePreviewImage").addEventListener("error", () => {
  $("#sourcePreviewLoading").classList.add("error");
  $("#sourcePreviewLoading").textContent = tr("Source preview is unavailable. Open the retained PDF instead.", "原单据预览暂不可用，请打开已保留的原 PDF。");
});
$("#documentTable").addEventListener("click", (event) => {
  const deleteButton = event.target.closest("[data-delete-document-id]");
  if (deleteButton && activeBatch) {
    const document = activeBatch.documents.find((item) => item.id === deleteButton.dataset.deleteDocumentId);
    if (!document || !confirm(tr(`Delete ${document.filename}?`, `删除 ${document.filename}？`))) return;
    api(`/api/v1/batch-documents/${document.id}`, { method: "DELETE" })
      .then(async () => { if (selectedDocument?.id === document.id) closeReview(); toast(tr("Document deleted.", "文件已删除。")); await selectBatch(activeBatch.id); })
      .catch((error) => toast(error.message));
    return;
  }
  const button = event.target.closest("[data-document-id]");
  if (!button || !activeBatch) return;
  selectedDocument = activeBatch.documents.find((item) => item.id === button.dataset.documentId) || null;
  renderDocuments();
  if (selectedDocument) renderReview(selectedDocument);
});
$("#documentTable").addEventListener("change", (event) => {
  const checkbox = event.target.closest("[data-select-document-id]");
  if (!checkbox || checkbox.disabled) return;
  if (checkbox.checked) selectedDocumentIds.add(checkbox.dataset.selectDocumentId);
  else selectedDocumentIds.delete(checkbox.dataset.selectDocumentId);
  renderDocuments();
});
$("#startBatchButton").addEventListener("click", async () => { if (!activeBatch?.staged_count) return; try { const result = await api(`/api/v1/batches/${activeBatch.id}/start`, { method: "POST" }); toast(tr(`${result.queued_count} files queued.`, `已将 ${result.queued_count} 份文件加入等待队列。`)); await selectBatch(activeBatch.id); } catch (error) { toast(error.message); } });
$("#deleteBatchButton").addEventListener("click", async () => { if (!activeBatch || !confirm(tr("Delete this batch and all encrypted PDFs and results?", "删除这个批次及其所有加密 PDF 和结果？"))) return; try { await api(`/api/v1/batches/${activeBatch.id}`, { method: "DELETE" }); activeBatch = null; selectedDocumentIds.clear(); closeReview(); await loadBatches(); renderActiveBatch(); } catch (error) { toast(error.message); } });
$("#retryButton").addEventListener("click", async () => { if (!selectedDocument) return; try { await api(`/api/v1/batch-documents/${selectedDocument.id}/retry`, { method: "POST" }); toast(tr("Queued for retry.", "已重新排队。")); await selectBatch(activeBatch.id); } catch (error) { toast(error.message); } });
$("#reviewForm").addEventListener("submit", async (event) => { event.preventDefault(); if (!selectedDocument?.result) return; const advance = event.submitter?.id === "saveNextReviewButton"; const queue = reviewCandidates(); const currentIndex = queue.findIndex((item) => item.id === selectedDocument.id); const nextId = queue.length > 1 ? queue[(Math.max(currentIndex, 0) + 1) % queue.length].id : null; const payload = {}; new FormData(event.currentTarget).forEach((value, key) => { payload[key] = numericFields.has(key) ? (value === "" ? null : Number(value)) : (value || null); }); try { await api(`/api/v1/batch-documents/${selectedDocument.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); toast(tr("Review saved.", "审核已保存。")); selectedDocument = null; await selectBatch(activeBatch.id); if (advance && nextId) { selectedDocument = activeBatch.documents.find((item) => item.id === nextId) || null; if (selectedDocument) renderReview(selectedDocument); } } catch (error) { toast(error.message); } });
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && $("#moreExportsMenu").open) {
    $("#moreExportsMenu").open = false;
    $("#moreExportsMenu summary").focus();
    return;
  }
  if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || $("#reviewForm").classList.contains("hidden")) return;
  if (event.key === "ArrowDown") { event.preventDefault(); moveReview(1); }
  if (event.key === "ArrowUp") { event.preventDefault(); moveReview(-1); }
});
document.addEventListener("click", (event) => {
  if ($("#moreExportsMenu").open && !$("#moreExportsMenu").contains(event.target)) $("#moreExportsMenu").open = false;
});

$("#batchSignOutButton").addEventListener("click", async () => {
  try { await fetch("/api/auth/logout", { method: "POST" }); } finally { location.replace("/login"); }
});

translate();
loadBatches().catch((error) => { $("#batchList").innerHTML = `<p class="muted">${escapeHtml(error.message)}</p>`; toast(error.message); });
