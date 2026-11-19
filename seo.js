const toggle = document.querySelector("#siteLanguage");
let language = window.ReceiptSiftLocale?.get() || "en";

function applyLanguage(next) {
  language = next;
  document.documentElement.lang = next === "en" ? "en" : "zh-CN";
  document.querySelectorAll("[data-en][data-zh]").forEach((element) => {
    element.textContent = element.dataset[next];
  });
  toggle.textContent = next === "en" ? "中文" : "English";
  document.title = next === "en" ? "PDF Receipt Parser & Bill Data Extractor | ReceiptSift" : "PDF 账单与收据解析工具 | ReceiptSift";
  window.ReceiptSiftLocale?.updateLinks();
}

window.ReceiptSiftLocale?.bindButton(toggle);
window.ReceiptSiftLocale?.subscribe((next) => applyLanguage(next));
applyLanguage(language);
