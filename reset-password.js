const form = document.querySelector("#resetForm");
const button = document.querySelector("#resetButton");
const status = document.querySelector("#resetStatus");
const token = new URLSearchParams(location.search).get("token") || "";
const locale = window.ReceiptSiftLocale;
const tr = (en, zh) => locale?.t(en, zh) || en;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  status.textContent = "";
  if (form.password.value !== form.confirmPassword.value) {
    status.textContent = tr("The two passwords do not match.", "两次输入的密码不一致。");
    return;
  }
  button.disabled = true;
  button.textContent = tr("Updating…", "正在更新…");
  try {
    const response = await fetch("/api/auth/password/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, password: form.password.value }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error?.message || tr("Unable to update the password.", "无法更新密码。"));
    location.replace(`/login?reset=1&lang=${locale?.get() || "en"}`);
  } catch (error) {
    status.textContent = error.message;
    button.disabled = false;
    button.textContent = tr("Update password", "更新密码");
  }
});
