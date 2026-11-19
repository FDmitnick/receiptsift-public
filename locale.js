(() => {
  const STORAGE_KEY = "receiptsift-language";
  const LEGACY_KEYS = ["receiptsift-site-language", "clearledger-language", "clearledger-site-language"];
  const listeners = new Set();
  const originalText = new WeakMap();
  const locales = {
    en: { label: "English", htmlLang: "en", dir: "ltr" },
    hi: { label: "हिन्दी", htmlLang: "hi", dir: "ltr" },
    es: { label: "Español", htmlLang: "es", dir: "ltr" },
    ar: { label: "العربية", htmlLang: "ar", dir: "rtl" },
    zh: { label: "简体中文", htmlLang: "zh-CN", dir: "ltr" },
  };
  const localeOrder = ["en", "hi", "es", "ar", "zh"];

  function normalize(value) {
    const candidate = String(value || "").toLowerCase().split("-")[0];
    return localeOrder.includes(candidate) ? candidate : "en";
  }
  function storedLanguage() {
    try {
      const query = new URLSearchParams(location.search).get("lang");
      if (localeOrder.includes(normalize(query)) && query) return normalize(query);
      const stored = localStorage.getItem(STORAGE_KEY) || LEGACY_KEYS.map((key) => localStorage.getItem(key)).find(Boolean);
      return normalize(stored || "en");
    } catch (_) { return "en"; }
  }

  let language = storedLanguage();

  const common = {
    "Resources": "资源", "How it works": "使用方式", "Privacy": "隐私", "Terms": "条款", "Cookies": "Cookie 说明",
    "Refunds": "退款规则", "Pricing": "价格", "Open app": "打开工作台", "Open workspace": "打开工作台",
    "Batch workspace": "批量工作台", "Single document": "单份解析", "Account": "账户", "Operations": "运营后台",
    "Sign in": "登录", "Sign out": "退出登录", "Create account": "创建账户", "Create free account": "创建免费账户",
    "Forgot password?": "忘记密码？", "Back to sign in →": "返回登录 →", "← Public site": "← 公开站点",
    "Private beta": "私密测试", "Private beta · Sign in": "私密测试 · 登录", "Request access": "申请试用",
    "Loading…": "加载中…", "Loading...": "加载中…", "Cancel": "取消", "Delete": "删除", "Save": "保存",
    "Close": "关闭", "Menu": "菜单", "Refresh": "刷新", "Help": "帮助", "English resources": "英文资源",
    "Home": "首页", "Product": "产品", "Product and workflow": "产品与工作流", "FEATURE GUIDE": "功能指南",
    "WORKFLOW": "工作流", "WORKFLOW GUIDE": "工作流指南", "STEP-BY-STEP GUIDE": "分步指南", "COMPARISON": "对比", "KEEP READING": "继续阅读",
    "HOW IT WORKS": "使用方式", "Skip to content": "跳到主要内容",
    "Contact": "联系", "App": "工作台", "Privacy-friendly analytics": "尊重隐私的匿名统计",
    "Help without leaving your work": "不离开工作台的帮助",
    "Get the next step here. Open the full guides only when you need more detail.": "先在这里找到下一步；需要更多细节时再打开完整指南。",
    "Parse one PDF": "解析一份 PDF", "Upload a PDF, compare extracted fields with the source, then export CSV.": "上传 PDF，对照原文核对提取字段，然后导出 CSV。",
    "Process a batch": "处理一个批次", "Add multiple PDFs, process them in the background, and review only the exceptions.": "加入多份 PDF，在后台处理，只复核异常文件。",
    "Know what is stored": "了解数据保留", "Single-document and batch content is encrypted for up to 7 days and can be deleted sooner.": "单份和批量内容均加密保存最多 7 天，也可提前删除。",
    "Open full guides": "查看完整指南", "Choose language": "选择语言",
    "Allow anonymous page and product-click measurement. We do not store raw IP addresses, browser fingerprints, or receipt contents.": "允许匿名统计页面访问与产品点击。我们不保存原始 IP、浏览器指纹或凭证内容。",
    "Decline": "拒绝", "Allow analytics": "允许匿名统计"
  };

  const additional = {
    hi: {
      "Single document": "एक दस्तावेज़", "Batch workspace": "बैच कार्यक्षेत्र", "Account": "खाता", "Operations": "संचालन", "Help": "सहायता",
      "Sign in": "साइन इन", "Sign out": "साइन आउट", "Delete": "हटाएँ", "Cancel": "रद्द करें", "Save": "सहेजें", "Close": "बंद करें",
      "ACCOUNT WORKSPACE": "खाता कार्यक्षेत्र", "Your data,": "आपका डेटा,", "accounted for.": "पूरी तरह स्पष्ट।", "SIGNED IN AS": "साइन इन खाता",
      "Private beta account": "निजी बीटा खाता", "RECEIPTS PARSED": "पार्स की गई रसीदें", "PAGES PROCESSED": "प्रसंस्कृत पृष्ठ", "CSV EXPORTS": "CSV निर्यात",
      "SINGLE-DOCUMENT STORAGE": "एकल दस्तावेज़ संग्रह", "OFF": "बंद", "SUBSCRIPTION": "सदस्यता", "View plans": "प्लान देखें",
      "Cancel subscription": "सदस्यता रद्द करें", "Diagnostic cases": "नैदानिक मामले", "Export your data.": "अपना डेटा निर्यात करें।",
      "Download account data": "खाता डेटा डाउनलोड करें", "Delete account.": "खाता हटाएँ।", "Delete account and all data": "खाता और सारा डेटा हटाएँ",
      "Member since": "सदस्यता आरंभ", "Order": "ऑर्डर", "Submitted": "जमा किया", "Deletes automatically": "स्वतः हटेगा", "Delete now": "अभी हटाएँ",
      "Loading…": "लोड हो रहा है…", "Loading...": "लोड हो रहा है…", "Refresh": "रीफ़्रेश", "Pricing": "मूल्य", "Privacy": "गोपनीयता", "Terms": "शर्तें",
      "Help without leaving your work": "काम छोड़े बिना सहायता", "Get the next step here. Open the full guides only when you need more detail.": "अगला कदम यहीं देखें। अधिक जानकारी के लिए पूरी गाइड खोलें।",
      "Parse one PDF": "एक PDF पार्स करें", "Upload a PDF, compare extracted fields with the source, then export CSV.": "PDF अपलोड करें, निकाले गए फ़ील्ड को स्रोत से मिलाएँ और CSV निर्यात करें।",
      "Process a batch": "बैच प्रोसेस करें", "Add multiple PDFs, process them in the background, and review only the exceptions.": "कई PDF जोड़ें, पृष्ठभूमि में प्रोसेस करें और केवल अपवादों की समीक्षा करें।",
      "Know what is stored": "जानें क्या सहेजा जाता है", "Single-document and batch content is encrypted for up to 7 days and can be deleted sooner.": "एकल और बैच सामग्री 7 दिनों तक एन्क्रिप्टेड रहती है और पहले हटाई जा सकती है।", "Open full guides": "पूरी गाइड खोलें"
    },
    es: {
      "Single document": "Documento individual", "Batch workspace": "Espacio por lotes", "Account": "Cuenta", "Operations": "Operaciones", "Help": "Ayuda",
      "Sign in": "Iniciar sesión", "Sign out": "Cerrar sesión", "Delete": "Eliminar", "Cancel": "Cancelar", "Save": "Guardar", "Close": "Cerrar",
      "ACCOUNT WORKSPACE": "ESPACIO DE CUENTA", "Your data,": "Tus datos,", "accounted for.": "claros y controlados.", "SIGNED IN AS": "SESIÓN INICIADA COMO",
      "Private beta account": "Cuenta beta privada", "RECEIPTS PARSED": "RECIBOS PROCESADOS", "PAGES PROCESSED": "PÁGINAS PROCESADAS", "CSV EXPORTS": "EXPORTACIONES CSV",
      "SINGLE-DOCUMENT STORAGE": "ALMACENAMIENTO INDIVIDUAL", "OFF": "DESACTIVADO", "SUBSCRIPTION": "SUSCRIPCIÓN", "View plans": "Ver planes",
      "Cancel subscription": "Cancelar suscripción", "Diagnostic cases": "Casos de diagnóstico", "Export your data.": "Exporta tus datos.",
      "Download account data": "Descargar datos de la cuenta", "Delete account.": "Eliminar cuenta.", "Delete account and all data": "Eliminar cuenta y todos los datos",
      "Member since": "Miembro desde", "Order": "Pedido", "Submitted": "Enviado", "Deletes automatically": "Se elimina automáticamente", "Delete now": "Eliminar ahora",
      "Loading…": "Cargando…", "Loading...": "Cargando…", "Refresh": "Actualizar", "Pricing": "Precios", "Privacy": "Privacidad", "Terms": "Términos",
      "Help without leaving your work": "Ayuda sin salir del trabajo", "Get the next step here. Open the full guides only when you need more detail.": "Consulta aquí el siguiente paso. Abre las guías completas cuando necesites más detalles.",
      "Parse one PDF": "Analizar un PDF", "Upload a PDF, compare extracted fields with the source, then export CSV.": "Sube un PDF, compara los campos con el original y exporta el CSV.",
      "Process a batch": "Procesar un lote", "Add multiple PDFs, process them in the background, and review only the exceptions.": "Añade varios PDF, procésalos en segundo plano y revisa solo las excepciones.",
      "Know what is stored": "Conoce qué se conserva", "Single-document and batch content is encrypted for up to 7 days and can be deleted sooner.": "El contenido individual y por lotes se cifra hasta 7 días y puede eliminarse antes.", "Open full guides": "Abrir guías completas"
    },
    ar: {
      "Single document": "مستند واحد", "Batch workspace": "مساحة الدُفعات", "Account": "الحساب", "Operations": "العمليات", "Help": "المساعدة",
      "Sign in": "تسجيل الدخول", "Sign out": "تسجيل الخروج", "Delete": "حذف", "Cancel": "إلغاء", "Save": "حفظ", "Close": "إغلاق",
      "ACCOUNT WORKSPACE": "مساحة الحساب", "Your data,": "بياناتك،", "accounted for.": "واضحة وتحت السيطرة.", "SIGNED IN AS": "الحساب الحالي",
      "Private beta account": "حساب تجريبي خاص", "RECEIPTS PARSED": "الإيصالات المعالجة", "PAGES PROCESSED": "الصفحات المعالجة", "CSV EXPORTS": "تصدير CSV",
      "SINGLE-DOCUMENT STORAGE": "تخزين المستند الواحد", "OFF": "متوقف", "SUBSCRIPTION": "الاشتراك", "View plans": "عرض الخطط",
      "Cancel subscription": "إلغاء الاشتراك", "Diagnostic cases": "حالات التشخيص", "Export your data.": "صدّر بياناتك.",
      "Download account data": "تنزيل بيانات الحساب", "Delete account.": "حذف الحساب.", "Delete account and all data": "حذف الحساب وجميع البيانات",
      "Member since": "عضو منذ", "Order": "الطلب", "Submitted": "أُرسل", "Deletes automatically": "يُحذف تلقائيًا", "Delete now": "احذف الآن",
      "Loading…": "جارٍ التحميل…", "Loading...": "جارٍ التحميل…", "Refresh": "تحديث", "Pricing": "الأسعار", "Privacy": "الخصوصية", "Terms": "الشروط",
      "Help without leaving your work": "مساعدة دون مغادرة عملك", "Get the next step here. Open the full guides only when you need more detail.": "اعرف الخطوة التالية هنا، وافتح الأدلة الكاملة عند الحاجة إلى تفاصيل إضافية.",
      "Parse one PDF": "حلّل ملف PDF واحدًا", "Upload a PDF, compare extracted fields with the source, then export CSV.": "ارفع ملف PDF وقارن الحقول بالمصدر ثم صدّر CSV.",
      "Process a batch": "عالج دُفعة", "Add multiple PDFs, process them in the background, and review only the exceptions.": "أضف عدة ملفات PDF وعالجها في الخلفية وراجع الاستثناءات فقط.",
      "Know what is stored": "اعرف ما يتم الاحتفاظ به", "Single-document and batch content is encrypted for up to 7 days and can be deleted sooner.": "يُشفّر محتوى المستندات الفردية والدُفعات لمدة تصل إلى 7 أيام ويمكن حذفه قبل ذلك.", "Open full guides": "فتح الأدلة الكاملة"
    }
  };

  const page = {
    "/": {
      "PRACTICAL RESOURCES": "实用资源",
      "Go from search question to finished CSV.": "从问题出发，得到可用的 CSV。",
      "PDF receipt parser": "PDF 凭证解析器",
      "What the parser extracts, which files it accepts, and where review still matters.": "了解可提取字段、支持的文件，以及仍需人工复核的环节。",
      "Explore the parser →": "了解解析能力 →",
      "WORKFLOW": "工作流",
      "Extract receipt data to CSV": "将凭证数据提取为 CSV",
      "See the current columns, sample output, and pre-export quality checks.": "查看当前字段、示例输出与导出前质量检查。",
      "See the CSV workflow →": "查看 CSV 工作流 →",
      "STEP-BY-STEP GUIDE": "分步指南",
      "How to extract PDF receipt data": "如何提取 PDF 凭证数据",
      "A six-step process from original PDF to reviewed spreadsheet rows.": "从原始 PDF 到已复核表格行的六步流程。",
      "Read the guide →": "阅读指南 →",
      "Parser vs. manual entry": "自动解析与手工录入对比",
      "Choose the right workflow for readable PDFs, irregular receipts, and consequential records.": "根据清晰 PDF、不规则凭证与重要记录选择合适流程。",
      "Compare the methods →": "对比两种方式 →",
      "Contact": "联系",
      "App": "工作台",
      "Privacy-friendly analytics": "尊重隐私的匿名统计",
      "Allow anonymous page and product-click measurement. We do not store raw IP addresses, browser fingerprints, or receipt contents.": "允许匿名统计页面访问与产品点击。我们不保存原始 IP、浏览器指纹或凭证内容。",
      "Decline": "拒绝",
      "Allow analytics": "允许匿名统计"
    },
    "/pricing": {
      "PRICING": "价格", "Start clear.": "先从清晰开始。", "Scale when you need it.": "需要时再升级。",
      "Single-document and batch source files, results, and corrections are encrypted for up to 7 days and can be deleted sooner.": "单份和批量源文件、结果与修改均加密保存最多 7 天，也可提前删除。",
      "FREE": "免费版", "For trying the complete workflow.": "用于体验完整工作流。", "PDF documents each month": "份 PDF / 月",
      "/month": "/月", "pages per PDF and": "页 / PDF，每月共", "pages per month": "页", "total pages each month": "页 / 月",
      "Up to": "单份最多", "pages per PDF": "页 / PDF", "Batch upload, up to": "单次批量上传最多", "PDFs at a time": "份 PDF",
      "Text and scanned PDF extraction": "文字型与扫描型 PDF 提取", "Source-linked review": "可对照原文复核", "CSV export": "CSV 导出",
      "MOST POPULAR": "最受欢迎", "For regular expense and bookkeeping work.": "适合日常费用与记账工作。",
      "For high-volume and batch processing.": "适合高频批量处理。", "Everything in Free": "包含免费版全部功能",
      "Everything in Plus": "包含 Plus 全部功能", "Choose Plus": "选择 Plus", "Choose Pro": "选择 Pro",
      "Subscription controls in your account": "在账户中管理订阅", "NO SURPRISE CHARGES": "没有意外费用",
      "Usage pauses at your monthly limit.": "达到月度限额后自动暂停。",
      "ReceiptSift pauses when either the document or page allowance is reached. There are no automatic overage fees, and both allowances reset each billing month.": "文件数或页数达到限额后，ReceiptSift 会暂停处理。不会自动收取超额费，额度每个计费月重置。"
    },
    "/login": {
      "Your receipts.": "你的凭证。", "Your workspace.": "你的工作台。", "Welcome back.": "欢迎回来。",
      "Sign in to your private receipt-review workspace.": "登录你的私密凭证复核工作台。",
      "EMAIL": "邮箱", "PASSWORD": "密码", "Create account →": "创建账户 →",
      "YOUR RECENT RECEIPTS STAY ENCRYPTED FOR 7 DAYS. KEEP ONLY REVIEWED STRUCTURED DATA IN YOUR LEDGER.": "最近单据加密保留 7 天。只有经你确认的结构化数据才会沉淀到长期台账。"
    },
    "/register": {
      "One account.": "一个账户。", "Clear retention.": "清晰的保留规则。", "Create your account.": "创建你的账户。",
      "Start a private receipt-review workspace with explicit single-document and batch retention.": "开始使用私密凭证复核工作台；单份与批量模式采用明确不同的保留规则。",
      "EMAIL": "邮箱", "PASSWORD · 12+ CHARACTERS": "密码 · 至少 12 个字符", "Sign in →": "登录 →",
      "SINGLE-DOCUMENT AND BATCH CONTENT IS ENCRYPTED FOR UP TO 7 DAYS AND CAN BE DELETED SOONER.": "单份和批量内容均加密保存最多 7 天，也可提前删除。"
    },
    "/forgot-password": {
      "Recover access.": "找回访问权。", "Keep control.": "保持掌控。", "Reset your password.": "重置密码。",
      "Enter your account email. We will send a secure reset link if the account exists.": "输入账户邮箱。如账户存在，我们会发送安全的重置链接。",
      "EMAIL": "邮箱", "Send reset link": "发送重置链接",
      "RESET LINKS ARE SINGLE-USE, EXPIRE AFTER 30 MINUTES, AND INVALIDATE EXISTING SESSIONS AFTER THE PASSWORD CHANGES.": "重置链接仅能使用一次，30 分钟后过期；密码更改后，现有会话全部失效。"
    },
    "/reset-password": {
      "A new key.": "一把新密钥。", "The same ledger.": "同一个账本。", "Choose a new password.": "设置新密码。",
      "Use at least 12 characters and do not reuse a password from another service.": "至少使用 12 个字符，不要与其他服务共用密码。",
      "NEW PASSWORD · 12+ CHARACTERS": "新密码 · 至少 12 个字符", "CONFIRM NEW PASSWORD": "确认新密码", "Update password": "更新密码",
      "YOUR NEW PASSWORD IS HASHED WITH ARGON2ID. COMPLETING THE RESET SIGNS OUT EVERY EXISTING SESSION.": "新密码使用 Argon2id 哈希保护。完成重置后，所有现有会话将退出。"
    },
    "/account": {
      "ACCOUNT WORKSPACE": "账户工作台", "Your data,": "你的数据，", "accounted for.": "清楚可查。", "SIGNED IN AS": "当前账户",
      "Private beta account": "私密测试账户", "RECEIPTS PARSED": "已解析凭证", "PAGES PROCESSED": "已处理页数",
      "CSV EXPORTS": "CSV 导出", "SINGLE-DOCUMENT STORAGE": "单份解析存储", "OFF": "关闭", "SUBSCRIPTION": "订阅",
      "View plans": "查看套餐", "Cancel subscription": "取消订阅", "Diagnostic cases": "诊断案例",
      "Loading diagnostic cases…": "正在加载诊断案例…", "Export your data.": "导出账户数据。", "Download account data": "下载账户数据",
      "Delete account.": "删除账户。", "Delete account and all data": "删除账户及全部数据",
      "Reports exist only when you explicitly submit one. Evidence is encrypted, expires after 14 days, and can be deleted sooner.": "只有在你主动提交报告时才会创建诊断案例。证据经过加密，14 天后过期，也可提前删除。",
      "Download your account profile, billing state, aggregate usage, parse-order metadata, and diagnostic-case metadata as JSON. Receipt files and extracted fields are not included.": "以 JSON 格式下载账户资料、计费状态、汇总用量、解析订单元数据与诊断案例元数据。不包含凭证文件与提取字段。",
      "This first cancels any active PayPal subscription, then deletes your account, sign-in records, billing mapping, aggregate usage, order metadata, and any encrypted diagnostic evidence. If PayPal cannot confirm cancellation, your account stays intact.": "系统会先取消活跃的 PayPal 订阅，再删除账户、登录记录、计费映射、汇总用量、订单元数据与加密诊断证据。如 PayPal 无法确认取消，账户会保持不变。"
    },
    "/resources": {
      "RECEIPTSIFT RESOURCES": "RECEIPTSIFT 资源", "Turn receipt PDFs into useful data.": "把凭证 PDF 变成可用数据。",
      "Product details, practical workflows, and honest comparisons for people who need receipt data in spreadsheets, expense records, or bookkeeping systems.": "面向需要将凭证数据用于电子表格、费用记录或记账系统的用户，提供产品说明、实用工作流与诚实对比。",
      "Built from the live product": "来自真实产品", "PDF receipt parser": "PDF 凭证解析器", "Explore the parser →": "了解解析能力 →",
      "Every guide reflects ReceiptSift's current extraction, review, CSV, and data-handling behavior.": "每篇指南都以 ReceiptSift 当前的提取、复核、CSV 与数据处理行为为准。",
      "Updated August 21, 2026": "更新于 2026 年 8 月 21 日", "/ Resources": "/ 资源",
      "See what ReceiptSift extracts, which PDFs it supports, and where human review still matters.": "查看 ReceiptSift 提取哪些字段、支持哪些 PDF，以及哪些环节仍需人工复核。",
      "Receipt to CSV": "凭证转 CSV", "See the CSV workflow →": "查看 CSV 工作流 →",
      "Understand the output columns and move reviewed receipt fields into a spreadsheet-ready file.": "了解输出字段，并将已复核的凭证数据整理为可直接用于表格的文件。",
      "Learn and decide": "学习与选择", "How to extract data from PDF receipts": "如何提取 PDF 凭证数据",
      "A practical six-step process for uploading, reviewing, reconciling, and exporting receipt data.": "一套用于上传、复核、核对与导出凭证数据的实用六步流程。",
      "Read the guide →": "阅读指南 →", "Receipt parser vs. manual entry": "自动解析与手工录入对比",
      "When automation helps, when typing by hand is safer, and why a reviewed workflow usually wins.": "了解何时自动化更合适、何时手工录入更安全，以及为什么经过复核的流程通常更可靠。",
      "Compare the workflows →": "对比工作流 →", "Start with a real PDF receipt.": "从一份真实 PDF 凭证开始。",
      "Upload a text-based or scanned PDF, review the extracted fields against the source, and export a clean CSV.": "上传文字型或扫描型 PDF，对照原文复核提取字段，然后导出整洁的 CSV。",
      "Open ReceiptSift": "打开 ReceiptSift"
    }
  };

  function routeCatalog() { return { ...common, ...(page[location.pathname] || {}) }; }
  function t(en, zh) {
    if (language === "zh") return zh || routeCatalog()[en] || en;
    return additional[language]?.[en] || en;
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, language);
      localStorage.setItem("receiptsift-site-language", language);
    } catch (_) { /* storage is optional */ }
  }

  function translateStatic(root = document) {
    const activeLocale = locales[language];
    document.documentElement.lang = activeLocale.htmlLang;
    document.documentElement.dir = activeLocale.dir;
    root.querySelectorAll?.("[data-en][data-zh]").forEach((node) => { node.textContent = t(node.dataset.en, node.dataset.zh); });
    const catalog = language === "zh" ? routeCatalog() : (additional[language] || {});
    const walker = document.createTreeWalker(root.body || root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (!node.parentElement || ["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA"].includes(node.parentElement.tagName)) return NodeFilter.FILTER_REJECT;
        return node.textContent.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });
    let node;
    while ((node = walker.nextNode())) {
      if (!originalText.has(node)) originalText.set(node, node.textContent);
      const source = originalText.get(node);
      const trimmed = source.trim();
      const translated = language === "en" ? null : catalog[trimmed];
      node.textContent = translated ? source.replace(trimmed, translated) : source;
    }
    document.querySelectorAll("[data-rs-en][data-rs-zh]").forEach((node) => { node.textContent = t(node.dataset.rsEn, node.dataset.rsZh); });
    document.querySelector("#receiptsiftConsent")?.setAttribute("aria-label", t("Analytics preference", "匿名统计偏好"));
    document.querySelectorAll("[data-locale-select], [data-locale-button], #siteLanguage, #languageButton, #languageToggle").forEach((control) => {
      if (control.tagName === "SELECT") control.value = language;
      control.setAttribute("aria-label", t("Choose language", "选择语言"));
    });
    syncHelpPanel();
    updateLinks();
    syncLanguageNote();
  }

  function syncHelpPanel() {
    const panel = document.querySelector("#rsHelpPanel");
    if (!panel) return;
    panel.innerHTML = `
      <div class="rs-help-heading"><h2 id="rsHelpTitle">${t("Help without leaving your work", "不离开工作台的帮助")}</h2><button class="rs-help-close" type="button" data-help-close>${t("Close", "关闭")}</button></div>
      <p class="rs-help-intro">${t("Get the next step here. Open the full guides only when you need more detail.", "先在这里找到下一步；需要更多细节时再打开完整指南。")}</p>
      <div class="rs-help-steps">
        <section><h3>${t("Parse one PDF", "解析一份 PDF")}</h3><p>${t("Upload a PDF, compare extracted fields with the source, then export CSV.", "上传 PDF，对照原文核对提取字段，然后导出 CSV。")}</p></section>
        <section><h3>${t("Process a batch", "处理一个批次")}</h3><p>${t("Add multiple PDFs, process them in the background, and review only the exceptions.", "加入多份 PDF，在后台处理，只复核异常文件。")}</p></section>
        <section><h3>${t("Know what is stored", "了解数据保留")}</h3><p>${t("Single-document and batch content is encrypted for up to 7 days and can be deleted sooner.", "单份和批量内容均加密保存最多 7 天，也可提前删除。")}</p></section>
      </div>
      <a class="rs-help-guides" href="/resources">${t("Open full guides", "查看完整指南")}</a>`;
  }

  function mountHelpPanel() {
    const triggers = [...document.querySelectorAll("[data-app-help]")];
    if (!triggers.length) return;
    const panel = document.createElement("aside");
    panel.id = "rsHelpPanel";
    panel.className = "rs-help-popover";
    panel.setAttribute("popover", "auto");
    panel.setAttribute("aria-labelledby", "rsHelpTitle");
    document.body.appendChild(panel);
    syncHelpPanel();
    panel.addEventListener("click", (event) => {
      if (event.target.closest("[data-help-close]")) panel.hidePopover?.();
    });
    panel.addEventListener("toggle", () => {
      const open = panel.matches(":popover-open");
      triggers.forEach((trigger) => trigger.setAttribute("aria-expanded", String(open)));
    });
    triggers.forEach((trigger) => {
      trigger.addEventListener("click", (event) => {
        if (!panel.showPopover) {
          if (trigger.tagName === "BUTTON") location.href = `/resources?lang=${language}`;
          return;
        }
        event.preventDefault();
        if (panel.matches(":popover-open")) panel.hidePopover();
        else panel.showPopover();
      });
    });
  }

  function syncLanguageNote() {
    const region = document.querySelector(".article-body, .legal");
    const existing = document.querySelector("[data-rs-language-note]");
    if (!region || language !== "zh") { existing?.remove(); return; }
    const note = existing || document.createElement("p");
    note.dataset.rsLanguageNote = "true";
    note.className = "rs-language-note";
    note.textContent = document.querySelector(".legal")
      ? "为避免法律含义偏差，完整政策文本目前以下方英文版为准。"
      : "该研究与指南正文目前仅提供英文版；页面导航与产品操作会继续保持中文。";
    if (!existing) region.prepend(note);
  }

  function updateLinks() {
    document.querySelectorAll("a[href]").forEach((link) => {
      const raw = link.getAttribute("href");
      if (!raw || raw.startsWith("#") || raw.startsWith("mailto:") || raw.startsWith("tel:") || raw.startsWith("javascript:")) return;
      try {
        const url = new URL(raw, location.origin);
        if (url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
        url.searchParams.set("lang", language);
        link.setAttribute("href", `${url.pathname}${url.search}${url.hash}`);
      } catch (_) { /* leave malformed links untouched */ }
    });
  }

  function set(next, { updateUrl = false } = {}) {
    const normalized = normalize(next);
    const changed = normalized !== language;
    language = normalized;
    persist();
    if (updateUrl) {
      const url = new URL(location.href);
      url.searchParams.set("lang", language);
      history.replaceState(history.state, "", `${url.pathname}${url.search}${url.hash}`);
    }
    translateStatic();
    if (changed) {
      listeners.forEach((listener) => listener(language));
      window.dispatchEvent(new CustomEvent("receiptsift:languagechange", { detail: { language } }));
    }
    return language;
  }

  function bindButton(control) {
    if (!control || control.dataset.rsLocaleBound) return;
    control.dataset.rsLocaleBound = "true";
    if (control.tagName === "SELECT") {
      control.addEventListener("change", () => set(control.value, { updateUrl: true }));
    } else {
      control.addEventListener("click", () => set(language === "en" ? "zh" : "en", { updateUrl: true }));
    }
  }

  function createSelect() {
    const select = document.createElement("select");
    select.className = "rs-locale-select";
    select.dataset.localeSelect = "true";
    localeOrder.forEach((code) => {
      const option = document.createElement("option");
      option.value = code;
      option.textContent = locales[code].label;
      select.appendChild(option);
    });
    return select;
  }

  function mountButton() {
    let button = document.querySelector("[data-locale-select], [data-locale-button], #siteLanguage, #languageButton, #languageToggle");
    if (button && button.tagName !== "SELECT") {
      const select = createSelect();
      select.id = button.id;
      select.className = `${button.className} rs-locale-select`.trim();
      button.replaceWith(select);
      button = select;
    }
    if (!button) {
      const target = document.querySelector(".pricing-nav, .account-nav > div, .legal-nav nav, .content-nav nav, header nav, .auth-panel");
      if (target) {
        button = createSelect();
        target.appendChild(button);
      }
    }
    bindButton(button);
  }

  async function accessState() {
    if (accessState.promise) return accessState.promise;
    accessState.promise = fetch("/api/auth/status", { headers: { Accept: "application/json" } })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("site_state_unavailable")))
      .then((state) => {
        document.documentElement.dataset.accessMode = state.access_mode || "accounts";
        document.documentElement.dataset.registrationOpen = String(Boolean(state.registration_open));
        document.querySelectorAll("[data-registration-action]").forEach((action) => {
          action.dataset.registrationOpen = String(Boolean(state.registration_open));
          action.setAttribute("href", state.registration_open ? `/register?lang=${language}` : `/login?registration=closed&lang=${language}`);
          action.dataset.rsEn = state.registration_open ? "Create free account" : "Private beta · Sign in";
          action.dataset.rsZh = state.registration_open ? "创建免费账户" : "私密测试 · 登录";
        });
        document.querySelectorAll("[data-registration-availability]").forEach((node) => {
          node.hidden = state.registration_open;
          node.dataset.rsEn = "ReceiptSift is currently in a private owner beta. Existing owner access can sign in; public registration is closed.";
          node.dataset.rsZh = "ReceiptSift 当前处于所有者私密测试阶段。已有所有者账户可登录，公开注册已关闭。";
        });
        translateStatic();
        window.dispatchEvent(new CustomEvent("receiptsift:accessstate", { detail: state }));
        return state;
      })
      .catch(() => null);
    return accessState.promise;
  }

  function subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); }

  window.ReceiptSiftLocale = { get: () => language, set, t, locales, localeOrder, subscribe, apply: translateStatic, updateLinks, bindButton, accessState };
  persist();
  document.addEventListener("DOMContentLoaded", () => {
    mountButton();
    mountHelpPanel();
    translateStatic();
    accessState();
  });
})();
