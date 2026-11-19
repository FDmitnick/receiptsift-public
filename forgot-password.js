const form = document.querySelector("#forgotForm");
const button = document.querySelector("#forgotButton");
const status = document.querySelector("#forgotStatus");
const locale = window.ReceiptSiftLocale;
const tr = (en, zh) => locale?.t(en, zh) || en;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  status.classList.remove("auth-success");
  status.textContent = "";
  button.disabled = true;
  button.textContent = tr("Sending…", "正在发送…");
  try {
    const response = await fetch("/api/auth/password/forgot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: form.email.value }),
    });
    if (!response.ok) throw new Error(tr("Unable to request a reset link.", "无法请求重置链接。"));
    status.classList.add("auth-success");
    status.textContent = tr("If that account exists, a reset email is on its way.", "如账户存在，重置邮件已在发送中。");
    button.textContent = tr("Email requested", "已请求邮件");
  } catch (error) {
    status.textContent = error.message;
    button.disabled = false;
    button.textContent = tr("Send reset link", "发送重置链接");
  }
});
