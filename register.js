const form = document.querySelector("#registerForm");
const button = document.querySelector("#registerButton");
const error = document.querySelector("#registerError");
const locale = window.ReceiptSiftLocale;
const tr = (en, zh) => locale?.t(en, zh) || en;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.textContent = "";
  button.disabled = true;
  button.textContent = tr("Creating…", "正在创建…");
  try {
    const response = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: form.email.value,
        password: form.password.value,
      }),
    });
    const payload = await response.json();
    if (!response.ok) {
      const localized = payload.error?.code === "owner_only_access" ? tr("Public registration is closed during the private beta.", "私密测试期间不开放公开注册。") : payload.error?.message;
      throw new Error(localized || tr("Unable to create the account.", "无法创建账户。"));
    }
    error.classList.add("auth-success");
    error.textContent = payload.email_sent
      ? tr("Account created. Check your email to verify it before signing in.", "账户已创建。请先查收验证邮件，再登录。")
      : tr("Account created, but email delivery is not configured yet. Contact support before signing in.", "账户已创建，但邮件发送尚未配置。登录前请联系支持。");
    form.email.disabled = true;
    form.password.disabled = true;
    button.textContent = tr("Check your email", "查收邮件");
  } catch (failure) {
    error.classList.remove("auth-success");
    error.textContent = failure.message;
    button.disabled = false;
    button.textContent = tr("Create account", "创建账户");
  }
});
