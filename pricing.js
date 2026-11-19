const subscribeButtons = [...document.querySelectorAll("[data-subscribe-plan]")];
const locale = window.ReceiptSiftLocale;
const tr = (en, zh) => locale?.t(en, zh) || en;
let billingConfig = null;
let currentUser = null;

function renderCheckoutAvailability() {
  if (!billingConfig) return;
  subscribeButtons.forEach((button) => {
    const plan = button.dataset.subscribePlan;
    const available = Boolean(billingConfig.checkout_available && billingConfig.plans?.[plan]?.paypal_plan_id);
    button.disabled = !available;
    button.dataset.rsEn = available ? `Choose ${plan[0].toUpperCase()}${plan.slice(1)}` : "Checkout unavailable";
    button.dataset.rsZh = available ? `选择 ${plan[0].toUpperCase()}${plan.slice(1)}` : "结账暂未开放";
    const message = document.querySelector(`#${plan}CheckoutMessage`);
    if (!available) {
      message.dataset.rsEn = "Private beta pricing is shown for transparency. Checkout is not active, and no charge can be made.";
      message.dataset.rsZh = "私密测试阶段展示价格仅供了解。结账尚未启用，不会产生扣款。";
    }
  });
  locale?.apply();
}

function loadPayPalSdk(clientId) {
  return new Promise((resolve, reject) => {
    if (window.paypal) return resolve(window.paypal);
    const script = document.createElement("script");
    const query = new URLSearchParams({
      "client-id": clientId,
      components: "buttons",
      vault: "true",
      intent: "subscription",
      currency: "USD",
    });
    script.src = `https://www.paypal.com/sdk/js?${query}`;
    script.onload = () => resolve(window.paypal);
    script.onerror = () => reject(new Error(tr("PayPal checkout could not be loaded.", "PayPal 结账组件加载失败。")));
    document.head.appendChild(script);
  });
}

async function jsonRequest(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error?.message || tr("The request failed.", "请求失败。"));
  return payload;
}

async function showCheckout(planCode) {
  const subscribeButton = document.querySelector(`[data-subscribe-plan="${planCode}"]`);
  const message = document.querySelector(`#${planCode}CheckoutMessage`);
  const container = `#paypal${planCode[0].toUpperCase()}${planCode.slice(1)}ButtonContainer`;
  message.textContent = "";
  if (!currentUser) {
    location.href = `/login?next=${encodeURIComponent(`/pricing?lang=${locale?.get() || "en"}`)}&lang=${locale?.get() || "en"}`;
    return;
  }
  if (!billingConfig?.checkout_available) {
    message.textContent = tr("PayPal checkout is not available yet. No charge was made.", "PayPal 结账尚未开放，不会产生扣款。");
    return;
  }
  subscribeButton.disabled = true;
  try {
    const paypal = await loadPayPalSdk(billingConfig.client_id);
    subscribeButton.classList.add("hidden");
    await paypal.Buttons({
      style: { color: "black", shape: "pill", label: "subscribe", height: 48 },
      createSubscription(_data, actions) {
        return actions.subscription.create({
          plan_id: billingConfig.plans[planCode].paypal_plan_id,
          custom_id: currentUser.id,
        });
      },
      async onApprove(data) {
        message.textContent = tr("Confirming your subscription…", "正在确认订阅…");
        const result = await jsonRequest("/api/billing/paypal/approve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ subscription_id: data.subscriptionID }),
        });
        if (result.entitlement.plan === planCode) {
          message.textContent = tr(`${planCode[0].toUpperCase()}${planCode.slice(1)} is active. Redirecting to your account…`, `${planCode[0].toUpperCase()}${planCode.slice(1)} 已生效，正在返回账户…`);
          setTimeout(() => location.assign("/account"), 900);
        } else {
          message.textContent = tr("PayPal is still confirming the subscription. Your account will update automatically.", "PayPal 仍在确认订阅，账户状态会自动更新。");
        }
      },
      onCancel() {
        message.textContent = tr("Checkout was cancelled. No charge was made.", "结账已取消，未产生扣款。");
      },
      onError() {
        message.textContent = tr("PayPal could not complete checkout. Please try again.", "PayPal 无法完成结账，请重试。");
      },
    }).render(container);
  } catch (error) {
    message.textContent = error.message;
    subscribeButton.disabled = false;
  }
}

async function initialize() {
  try {
    const [config, auth] = await Promise.all([
      jsonRequest("/api/billing/config"),
      jsonRequest("/api/auth/status"),
    ]);
    billingConfig = config;
    currentUser = auth.authenticated ? auth.user : null;
    const authAction = document.querySelector("#pricingAuthAction");
    authAction.href = currentUser ? "/batches" : "/login?next=/pricing";
    authAction.dataset.rsEn = currentUser ? "Open workspace" : "Sign in";
    authAction.dataset.rsZh = currentUser ? "打开工作台" : "登录";
    document.querySelector("#freeDocuments").textContent = config.plans.free.monthly_documents;
    document.querySelector("#freePages").textContent = config.plans.free.monthly_pages;
    document.querySelector("#freePagesPerDocument").textContent = config.plans.free.max_pages_per_document;
    document.querySelector("#plusDocuments").textContent = config.plans.plus.monthly_documents;
    document.querySelector("#plusPages").textContent = config.plans.plus.monthly_pages;
    document.querySelector("#plusPagesPerDocument").textContent = config.plans.plus.max_pages_per_document;
    document.querySelector("#plusBatchFiles").textContent = config.plans.plus.max_files_per_batch;
    document.querySelector("#plusPrice").textContent = Number(config.plans.plus.price).toLocaleString(locale?.get() === "zh" ? "zh-CN" : "en-US");
    document.querySelector("#proDocuments").textContent = config.plans.pro.monthly_documents;
    document.querySelector("#proPages").textContent = config.plans.pro.monthly_pages;
    document.querySelector("#proPagesPerDocument").textContent = config.plans.pro.max_pages_per_document;
    document.querySelector("#proBatchFiles").textContent = config.plans.pro.max_files_per_batch;
    document.querySelector("#proPrice").textContent = Number(config.plans.pro.price).toLocaleString(locale?.get() === "zh" ? "zh-CN" : "en-US");
    renderCheckoutAvailability();
  } catch (_error) {
    subscribeButtons.forEach((button) => { button.disabled = true; });
    document.querySelector("#plusCheckoutMessage").textContent = tr("Pricing configuration is not available yet.", "价格配置暂不可用。");
  }
}

subscribeButtons.forEach((button) => button.addEventListener("click", () => showCheckout(button.dataset.subscribePlan)));
locale?.subscribe(renderCheckoutAvailability);
initialize();
