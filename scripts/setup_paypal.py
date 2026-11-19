from __future__ import annotations

import os

from backend.billing import BillingSettings, PayPalClient


def main() -> None:
    settings = BillingSettings()
    if settings.paypal_environment != "sandbox" and os.getenv("PAYPAL_SETUP_ALLOW_LIVE") != "yes":
        raise SystemExit("Refusing to create live PayPal resources. Set PAYPAL_SETUP_ALLOW_LIVE=yes only after sandbox acceptance.")
    client = PayPalClient(settings)
    product_id = os.getenv("PAYPAL_PRODUCT_ID", "").strip()
    if not product_id:
        product = client.create_product()
        product_id = str(product["id"])
        print(f"PAYPAL_PRODUCT_ID={product_id}")
    else:
        print(f"Using PAYPAL_PRODUCT_ID={product_id}")

    for plan_code, configured_plan_id in (
        ("plus", settings.paypal_plus_plan_id),
        ("pro", settings.paypal_pro_plan_id),
    ):
        variable_name = f"PAYPAL_{plan_code.upper()}_PLAN_ID"
        if not configured_plan_id:
            plan = client.create_monthly_plan(product_id, plan_code)
            print(f"{variable_name}={plan['id']}")
        else:
            print(f"Using {variable_name}={configured_plan_id}")

    webhook_url = os.getenv("PAYPAL_WEBHOOK_URL", "").strip()
    if webhook_url and not settings.paypal_webhook_id:
        webhook = client.create_webhook(webhook_url)
        print(f"PAYPAL_WEBHOOK_ID={webhook['id']}")
    elif settings.paypal_webhook_id:
        print(f"Using PAYPAL_WEBHOOK_ID={settings.paypal_webhook_id}")
    else:
        print("PAYPAL_WEBHOOK_ID not created: set PAYPAL_WEBHOOK_URL and run again.")

    print("Copy the generated IDs into Railway variables. Never print or copy PAYPAL_CLIENT_SECRET into logs.")


if __name__ == "__main__":
    main()
