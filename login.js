const form = document.querySelector("#loginForm");
const button = document.querySelector("#loginButton");
const error = document.querySelector("#loginError");
const query = new URLSearchParams(location.search);
const locale = window.ReceiptSiftLocale;
const tr = (en, zh) => locale?.t(en, zh) || en;
const requested = query.get("next");
let access = null;
const policyLinks = document.createElement("p");
policyLinks.className = "login-policy";
policyLinks.innerHTML = '<a href="/privacy">Privacy</a> · <a href="/terms">Terms</a> · <a href="/cookies">Cookies</a> · <a href="/refunds">Refunds</a> · <a href="mailto:contact@example.invalid">Contact</a>';
form.appendChild(policyLinks);

function safeTarget(value) { return value && value.startsWith("/") && !value.startsWith("//") ? value : `/batches?lang=${locale?.get() || "en"}`; }
function localizedError(code, fallback) {
  const messages = {
    invalid_credentials: ["Email or password is incorrect.", "邮箱或密码不正确。"],
    email_not_verified: ["Verify your email before signing in.", "请先完成邮箱验证再登录。"],
    owner_only_access: ["ReceiptSift is currently restricted to the site owner.", "ReceiptSift 当前仅限所有者使用。"],
    rate_limit_reached: ["Too many attempts. Try again later.", "尝试次数过多，请稍后再试。"]
  };
  return messages[code] ? tr(...messages[code]) : fallback || tr("Unable to sign in.", "无法登录，请重试。");
}

function renderLoginContext() {
  const context = document.querySelector("#loginContext");
  if (requested?.startsWith("/batches")) context.textContent = tr("Sign in to continue to your batch workspace.", "登录后继续进入批量工作台。");
  else if (requested?.startsWith("/app")) context.textContent = tr("Sign in to parse and review one document.", "登录后解析并复核单份文件。");
  else context.textContent = tr("Sign in to your private receipt-review workspace.", "登录你的私密凭证复核工作台。");
  if (query.get("registration") === "closed" || access?.registration_open === false) {
    const notice = document.querySelector("#accessNotice");
    notice.hidden = false;
    notice.textContent = tr("ReceiptSift is in a private owner beta. Public registration is closed; existing owner access can sign in.", "ReceiptSift 正处于所有者私密测试阶段。公开注册已关闭，已有所有者账户可继续登录。");
    document.querySelector("#registerLink").hidden = true;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  access = await locale?.accessState();
  renderLoginContext();
});
locale?.subscribe(renderLoginContext);
if (query.get("verified") === "1") {
  error.classList.add("auth-success");
  error.textContent = tr("Email verified. You can sign in now.", "邮箱已验证，现在可以登录。");
} else if (query.get("verification") === "invalid") {
  error.textContent = tr("That verification link is invalid or expired.", "该验证链接无效或已过期。");
} else if (query.get("reset") === "1") {
  error.classList.add("auth-success");
  error.textContent = tr("Password updated. Sign in with your new password.", "密码已更新，请使用新密码登录。");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  error.classList.remove("auth-success");
  error.textContent = "";
  button.disabled = true;
  button.textContent = "Checking…";
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: form.email.value, password: form.password.value }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(localizedError(payload.error?.code, payload.error?.message));
    location.replace(safeTarget(requested));
  } catch (failure) {
    error.textContent = failure.message;
    form.password.select();
    button.disabled = false;
    button.textContent = tr("Continue", "继续");
  }
});
