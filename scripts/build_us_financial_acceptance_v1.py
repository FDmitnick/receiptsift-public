from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
DEFAULT_SOURCE = WORKSPACE / "收据账单数据" / "美国现代专项测试集200份_2020-2026"
DEFAULT_OUTPUT = WORKSPACE / "收据账单数据" / "美国财务文档验收集275份_Schema_v1_2020-2026"

COMMON_FIELDS = (
    "vendor_name",
    "vendor_address",
    "vendor_tax_id",
    "customer_name",
    "customer_address",
    "document_number",
    "issue_date",
    "due_date",
    "currency",
    "account_number",
    "purchase_order_number",
    "payment_terms",
    "card_last4",
    "payment_method",
)
AMOUNT_FIELDS = (
    "gross_amount",
    "discount",
    "refund",
    "subtotal",
    "shipping",
    "fees",
    "tax",
    "tip",
    "total",
    "amount_paid",
    "balance_due",
    "previous_balance",
    "payments",
    "credits",
    "adjustments",
    "current_charges",
    "late_fee",
    "minimum_due",
)
BILL_FIELDS = ("service_period_start", "service_period_end", "autopay_date")
ALL_FIELDS = COMMON_FIELDS + AMOUNT_FIELDS + BILL_FIELDS

STATES = [
    ("CA", 0.0725),
    ("TX", 0.0625),
    ("NY", 0.04),
    ("FL", 0.06),
    ("WA", 0.065),
    ("IL", 0.0625),
    ("MA", 0.0625),
    ("CO", 0.029),
    ("GA", 0.04),
    ("AZ", 0.056),
]

INVOICE_PROFILES = [
    (
        "product_purchase",
        "Summit Office Supply LLC",
        "425 Market Street, Denver, CO 80202",
        ["Ergonomic Chair", "Standing Desk", "Monitor Arm", "Printer Paper", "USB-C Dock"],
    ),
    (
        "professional_services",
        "Blue Harbor Consulting LLC",
        "88 Franklin Avenue, Boston, MA 02110",
        ["Strategy Workshop", "Research Hours", "Data Analysis", "Implementation Support", "Project Management"],
    ),
    (
        "logistics_freight",
        "Interstate Freight Partners Inc.",
        "2300 Commerce Road, Dallas, TX 75201",
        ["Line Haul", "Fuel Surcharge", "Liftgate Service", "Warehouse Handling", "Final Mile Delivery"],
    ),
    (
        "construction_maintenance",
        "Redwood Facility Services LLC",
        "710 Mission Street, San Francisco, CA 94103",
        ["Preventive Maintenance", "Replacement Parts", "Electrical Labor", "Site Inspection", "Emergency Callout"],
    ),
    (
        "software_subscription",
        "Cloud Mesa Software Inc.",
        "500 Pine Street, Seattle, WA 98101",
        ["Platform Subscription", "User Licenses", "API Usage", "Premium Support", "Data Retention Add-on"],
    ),
    (
        "medical_services",
        "Lakeside Clinical Services PC",
        "1400 Lake Shore Drive, Chicago, IL 60601",
        ["Clinical Consultation", "Laboratory Service", "Diagnostic Imaging", "Administrative Fee", "Follow-up Visit"],
    ),
]

BILL_PROFILES = [
    ("utility", "North City Electric", "100 Power Plaza, Phoenix, AZ 85004", ["Electric Supply", "Delivery Charge", "Grid Adjustment"]),
    ("utility", "Clearwater Municipal Services", "55 Civic Center Way, Tampa, FL 33602", ["Water Service", "Wastewater", "Solid Waste"]),
    ("telecom", "MetroWave Communications", "900 Network Drive, Atlanta, GA 30303", ["Monthly Plan", "Device Payment", "Data Add-on"]),
    (
        "credit_card_statement",
        "Continental Community Bank",
        "1 Financial Center, New York, NY 10005",
        ["Purchases", "Cash Advance", "Interest Charge"],
    ),
]

CUSTOMERS = [
    ("Pioneer Retail Group", "1200 Broadway, New York, NY 10001"),
    ("Cedar Works Studio", "77 King Street, Seattle, WA 98104"),
    ("Bright Path Learning", "310 Congress Avenue, Austin, TX 78701"),
    ("Greenfield Property Co.", "415 Adams Street, Chicago, IL 60606"),
    ("Harbor Medical Partners", "28 State Street, Boston, MA 02109"),
]


def _money(value: float) -> float:
    return round(value + 1e-9, 2)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _empty_fields() -> dict[str, Any]:
    return {name: None for name in ALL_FIELDS}


def _line_item(description: str, quantity: float, unit_price: float) -> dict[str, Any]:
    return {
        "description": description,
        "sku": None,
        "quantity": quantity,
        "unit": "each" if quantity.is_integer() else "hour",
        "unit_price": _money(unit_price),
        "discount": 0.0,
        "tax_rate": None,
        "tax_amount": None,
        "amount": _money(quantity * unit_price),
    }


def _ground_truth(
    *,
    sample_id: str,
    document_type: str,
    document_subtype: str,
    category: str,
    year: int,
    page_count: int,
    fields: dict[str, Any],
    line_items: list[dict[str, Any]],
    source_type: str,
    source_provider: str,
    source_url: str | None,
    ground_truth_status: str,
    authenticity_status: str,
    state: str | None,
    pdf_type: str,
    core_bill: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "sample_id": sample_id,
        "document_type": document_type,
        "document_subtype": document_subtype,
        "category": category,
        "source": {
            "type": source_type,
            "provider": source_provider,
            "url": source_url,
            "ground_truth_status": ground_truth_status,
            "authenticity_status": authenticity_status,
        },
        "document": {
            "country": "United States",
            "state": state,
            "year": year,
            "year_basis": "transaction_or_statement_date" if ground_truth_status == "exact" else "official_source_document",
            "page_count": page_count,
            "pdf_type": pdf_type,
        },
        "fields": {name: fields.get(name) for name in ALL_FIELDS},
        "line_items": line_items,
        "features": {
            "usd": fields.get("currency") == "USD",
            "multi_page": page_count > 1,
            "core_bill": core_bill,
            "synthetic": source_type == "synthetic_controlled",
        },
    }


def _fit_image(page: pymupdf.Page, image_path: Path) -> None:
    with Image.open(image_path) as image:
        width, height = image.size
    scale = min(page.rect.width / width, page.rect.height / height)
    rendered_width = width * scale
    rendered_height = height * scale
    x0 = (page.rect.width - rendered_width) / 2
    y0 = (page.rect.height - rendered_height) / 2
    page.insert_image(pymupdf.Rect(x0, y0, x0 + rendered_width, y0 + rendered_height), filename=str(image_path))


def _images_to_pdf(images: list[Path], output: Path) -> None:
    document = pymupdf.open()
    for image_path in images:
        page = document.new_page(width=612, height=792)
        _fit_image(page, image_path)
    document.save(output, deflate=True, garbage=4)
    document.close()


def _render_preview(pdf_path: Path, output: Path) -> None:
    document = pymupdf.open(pdf_path)
    pixmap = document[0].get_pixmap(matrix=pymupdf.Matrix(1.1, 1.1), alpha=False)
    pixmap.save(output)
    document.close()


def _contact_sheet(output: Path) -> None:
    previews = []
    for truth_path in sorted(output.rglob("ground_truth.v1.json")):
        preview = next(truth_path.parent.glob("preview.*"), None)
        if preview is not None:
            previews.append((truth_path.parent.name, preview))
    columns = 8
    cell_width, cell_height = 180, 250
    rows = math.ceil(len(previews) / columns)
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (sample_id, preview_path) in enumerate(previews):
        with Image.open(preview_path) as image:
            thumbnail = image.convert("RGB")
            thumbnail.thumbnail((cell_width - 16, cell_height - 38))
        x = (index % columns) * cell_width + (cell_width - thumbnail.width) // 2
        y = (index // columns) * cell_height + 24
        sheet.paste(thumbnail, (x, y))
        draw.text(((index % columns) * cell_width + 6, (index // columns) * cell_height + 5), sample_id, fill="black")
    sheet.save(output / "preview_contact_sheet.jpg", quality=86, optimize=True)


def _legacy_document_type(category: str, group: str) -> tuple[str, str, bool]:
    if category == "utility_bill":
        return "bill", "legacy_receipt_style_utility", False
    if category == "telecom_bill":
        return "bill", "legacy_receipt_style_telecom", False
    if category == "credit_card":
        return "bill", "legacy_receipt_style_credit_card", False
    if "utility_bill" in category or group == "official_modern_sample_page":
        return "bill", "official_bill_guide_page", False
    return "receipt", category, False


def _migrate_legacy_expected(raw: dict[str, Any], manifest_row: dict[str, str]) -> dict[str, Any]:
    category = raw.get("category") or manifest_row.get("category") or "unknown"
    group = manifest_row.get("group") or raw.get("source_type") or "existing_200"
    document_type, subtype, core_bill = _legacy_document_type(category, group)
    exact = raw.get("ground_truth_status") == "exact"
    fields = _empty_fields()
    if exact:
        mapping = {
            "merchant": "vendor_name",
            "receipt_number": "document_number",
            "date": "issue_date",
            "currency": "currency",
            "card_last4": "card_last4",
            "payment_method": "payment_method",
            "gross_amount": "gross_amount",
            "discount": "discount",
            "refund": "refund",
            "subtotal": "subtotal",
            "tax": "tax",
            "tip": "tip",
            "total": "total",
        }
        for old_name, new_name in mapping.items():
            fields[new_name] = raw.get(old_name)
        if document_type == "bill":
            fields["balance_due"] = raw.get("total")
    items = []
    if exact:
        for item in raw.get("items") or []:
            items.append(
                {
                    "description": item.get("description"),
                    "sku": None,
                    "quantity": None,
                    "unit": None,
                    "unit_price": None,
                    "discount": None,
                    "tax_rate": None,
                    "tax_amount": None,
                    "amount": item.get("amount"),
                }
            )
    source_type = "synthetic_controlled" if exact else "official_public_sample"
    return _ground_truth(
        sample_id=raw["sample_id"],
        document_type=document_type,
        document_subtype=subtype,
        category=category,
        year=int(raw.get("document_year") or manifest_row.get("document_year") or 2021),
        page_count=int(raw.get("page_count") or manifest_row.get("page_count") or 1),
        fields=fields,
        line_items=items,
        source_type=source_type,
        source_provider=manifest_row.get("source_provider") or "locally generated controlled fixture",
        source_url=manifest_row.get("source_url") or None,
        ground_truth_status="exact" if exact else "flow_only",
        authenticity_status=raw.get("authenticity_status")
        or ("synthetic not a real transaction" if exact else "official example or guide; not a private transaction"),
        state=raw.get("state"),
        pdf_type="image_only",
        core_bill=core_bill,
    )


def _draw_page(page: pymupdf.Page, lines: list[tuple[str, float, bool]]) -> None:
    page.draw_rect(page.rect, color=(0.12, 0.19, 0.28), width=1.2)
    y = 42.0
    for text, size, bold in lines:
        font = "hebo" if bold else "helv"
        page.insert_text((48, y), text, fontsize=size, fontname=font, color=(0.06, 0.09, 0.13))
        y += max(size + 7, 17)
    page.insert_text((155, 770), "SYNTHETIC TEST DOCUMENT - NOT VALID", fontsize=12, fontname="hebo", color=(0.72, 0.0, 0.0))


def _write_pdf(page_lines: list[list[tuple[str, float, bool]]], output: Path, image_only: bool) -> None:
    source = pymupdf.open()
    for lines in page_lines:
        page = source.new_page(width=612, height=792)
        _draw_page(page, lines)
    if not image_only:
        source.save(output, deflate=True, garbage=4)
        source.close()
        return
    scanned = pymupdf.open()
    for page in source:
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0), alpha=False)
        target = scanned.new_page(width=612, height=792)
        target.insert_image(target.rect, stream=pixmap.tobytes("jpeg", jpg_quality=86))
    scanned.save(output, deflate=True, garbage=4)
    scanned.close()
    source.close()


def _invoice_fixture(index: int, rng: random.Random) -> tuple[dict[str, Any], list[list[tuple[str, float, bool]]]]:
    profile = INVOICE_PROFILES[(index - 1) % len(INVOICE_PROFILES)]
    subtype, vendor, vendor_address, descriptions = profile
    customer_name, customer_address = CUSTOMERS[(index - 1) % len(CUSTOMERS)]
    state, tax_rate = STATES[(index - 1) % len(STATES)]
    year = 2020 + ((index - 1) % 7)
    issue = date(year, ((index * 3) % 12) + 1, ((index * 7) % 24) + 1)
    terms_days = (15, 30, 45)[(index - 1) % 3]
    due = issue + timedelta(days=terms_days)
    count = 3 + (index % 3)
    items = []
    for item_index in range(count):
        quantity = float(1 + ((index + item_index) % 5))
        unit_price = _money(24 + rng.random() * 240)
        items.append(_line_item(descriptions[item_index % len(descriptions)], quantity, unit_price))
    subtotal = _money(sum(item["amount"] for item in items))
    discount = _money(subtotal * 0.05) if index % 4 == 0 else 0.0
    shipping = _money(12 + index * 0.75) if subtype in {"product_purchase", "logistics_freight"} else 0.0
    fees = _money(8.5 + index * 0.25) if index % 6 == 0 else 0.0
    tax = _money((subtotal - discount) * tax_rate)
    total = _money(subtotal - discount + shipping + fees + tax)
    amount_paid = _money(total * 0.25) if index % 5 == 0 else 0.0
    balance_due = _money(total - amount_paid)
    sample_id = f"US-FIN-INV-{index:03d}"
    fields = _empty_fields()
    fields.update(
        {
            "vendor_name": vendor,
            "vendor_address": vendor_address,
            "vendor_tax_id": f"EIN 9{index:02d}-00{index:04d}",
            "customer_name": customer_name,
            "customer_address": customer_address,
            "document_number": f"INV-{year}-{1000 + index}",
            "issue_date": issue.isoformat(),
            "due_date": due.isoformat(),
            "currency": "USD",
            "account_number": f"AC-{(index * 7919) % 1000000:06d}",
            "purchase_order_number": f"PO-{year}-{5000 + index}",
            "payment_terms": f"Net {terms_days}",
            "gross_amount": subtotal,
            "discount": discount,
            "subtotal": subtotal,
            "shipping": shipping,
            "fees": fees,
            "tax": tax,
            "total": total,
            "amount_paid": amount_paid,
            "balance_due": balance_due,
        }
    )
    image_only = index % 2 == 0
    page_count = 2 if index % 4 == 0 else 1
    header = [
        (vendor, 19, True),
        (vendor_address, 10, False),
        (fields["vendor_tax_id"], 10, False),
        ("INVOICE", 22, True),
        (f"Invoice No: {fields['document_number']}", 11, False),
        (f"Issue Date: {fields['issue_date']}", 11, False),
        (f"Due Date: {fields['due_date']}", 11, False),
        (f"Payment Terms: {fields['payment_terms']}", 11, False),
        (f"Account Number: {fields['account_number']}", 11, False),
        (f"PO Number: {fields['purchase_order_number']}", 11, False),
        (f"Bill To: {customer_name}", 11, True),
        (customer_address, 10, False),
        ("DESCRIPTION    QTY x UNIT PRICE    AMOUNT", 10, True),
    ]
    item_lines = [
        (f"{item['description']} {item['quantity']:.0f} x {item['unit_price']:.2f} {item['amount']:.2f}", 10, False) for item in items
    ]
    summary = [
        (f"Subtotal USD {subtotal:.2f}", 11, False),
        (f"Discount USD {discount:.2f}", 11, False),
        (f"Shipping USD {shipping:.2f}", 11, False),
        (f"Fees USD {fees:.2f}", 11, False),
        (f"Sales Tax ({state}) USD {tax:.2f}", 11, False),
        (f"Invoice Total USD {total:.2f}", 13, True),
        (f"Amount Paid USD {amount_paid:.2f}", 11, False),
        (f"Balance Due USD {balance_due:.2f}", 14, True),
    ]
    if page_count == 1:
        pages = [header + item_lines + summary]
    else:
        pages = [header + item_lines[:2] + [("Line items continue on page 2", 10, False)]]
        pages.append([(vendor, 16, True), (f"Invoice No: {fields['document_number']} - Page 2", 11, False)] + item_lines[2:] + summary)
    truth = _ground_truth(
        sample_id=sample_id,
        document_type="invoice",
        document_subtype=subtype,
        category="invoice",
        year=year,
        page_count=page_count,
        fields=fields,
        line_items=items,
        source_type="synthetic_controlled",
        source_provider="ReceiptSift locally generated controlled fixture",
        source_url=None,
        ground_truth_status="exact",
        authenticity_status="synthetic not a real transaction",
        state=state,
        pdf_type="image_only" if image_only else "searchable_text",
    )
    return truth, pages


def _bill_fixture(index: int, rng: random.Random) -> tuple[dict[str, Any], list[list[tuple[str, float, bool]]]]:
    subtype, vendor, vendor_address, charge_names = BILL_PROFILES[(index - 1) % len(BILL_PROFILES)]
    customer_name, customer_address = CUSTOMERS[(index + 1) % len(CUSTOMERS)]
    state, tax_rate = STATES[(index + 3) % len(STATES)]
    year = 2020 + ((index - 1) % 7)
    issue = date(year, ((index * 5) % 12) + 1, ((index * 11) % 23) + 1)
    period_end = issue - timedelta(days=2)
    period_start = period_end - timedelta(days=29)
    due = issue + timedelta(days=21)
    previous = _money(30 + rng.random() * 180)
    payments = previous if index % 4 else _money(previous * 0.75)
    credits = _money(5 + rng.random() * 20) if index % 5 == 0 else 0.0
    current = _money(60 + rng.random() * 260)
    adjustments = _money(4.5) if index % 6 == 0 else 0.0
    fees = _money(7.0) if index % 3 == 0 else 0.0
    late_fee = _money(12.0) if index % 7 == 0 else 0.0
    tax = _money(current * tax_rate)
    balance_due = _money(previous - payments - credits + current + adjustments + fees + late_fee + tax)
    minimum_due = _money(max(25.0, balance_due * 0.08)) if subtype == "credit_card_statement" else None
    sample_id = f"US-FIN-BILL-{index:03d}"
    fields = _empty_fields()
    fields.update(
        {
            "vendor_name": vendor,
            "vendor_address": vendor_address,
            "customer_name": customer_name,
            "customer_address": customer_address,
            "document_number": f"STMT-{year}-{7000 + index}",
            "issue_date": issue.isoformat(),
            "due_date": due.isoformat(),
            "currency": "USD",
            "account_number": f"AC-{(index * 3571) % 1000000:06d}",
            "payment_terms": "Due on stated date",
            "tax": tax,
            "total": balance_due,
            "balance_due": balance_due,
            "previous_balance": previous,
            "payments": payments,
            "credits": credits,
            "adjustments": adjustments,
            "current_charges": current,
            "fees": fees,
            "late_fee": late_fee,
            "minimum_due": minimum_due,
            "service_period_start": period_start.isoformat(),
            "service_period_end": period_end.isoformat(),
        }
    )
    image_only = index % 2 == 1
    page_count = 2 if index % 5 == 0 else 1
    line_items = []
    remaining = current
    for item_index, name in enumerate(charge_names):
        amount = remaining if item_index == len(charge_names) - 1 else _money(current * (0.45 if item_index == 0 else 0.3))
        remaining = _money(remaining - amount)
        line_items.append(_line_item(name, 1.0, amount))
    title = "CREDIT CARD STATEMENT" if subtype == "credit_card_statement" else "MONTHLY BILL STATEMENT"
    header = [
        (vendor, 19, True),
        (vendor_address, 10, False),
        (title, 20, True),
        (f"Statement Number: {fields['document_number']}", 11, False),
        (f"Account Number: {fields['account_number']}", 11, False),
        (f"Statement Date: {fields['issue_date']}", 11, False),
        (f"Due Date: {fields['due_date']}", 11, False),
        (f"Service Period: {period_start.isoformat()} to {period_end.isoformat()}", 11, False),
        (f"Customer: {customer_name}", 11, True),
        (customer_address, 10, False),
    ]
    charges = [(f"{item['description']} USD {item['amount']:.2f}", 10, False) for item in line_items]
    summary = [
        (f"Previous Balance USD {previous:.2f}", 11, False),
        (f"Payments USD {payments:.2f}", 11, False),
        (f"Credits USD {credits:.2f}", 11, False),
        (f"Current Charges USD {current:.2f}", 11, False),
        (f"Adjustments USD {adjustments:.2f}", 11, False),
        (f"Fees USD {fees:.2f}", 11, False),
        (f"Late Fee USD {late_fee:.2f}", 11, False),
        (f"Tax USD {tax:.2f}", 11, False),
    ]
    if minimum_due is not None:
        summary.append((f"Minimum Due USD {minimum_due:.2f}", 11, False))
    summary.append((f"Amount Due USD {balance_due:.2f}", 14, True))
    if page_count == 1:
        pages = [header + charges + summary]
    else:
        pages = [header + [("Charge detail continues on page 2", 10, False)]]
        pages.append([(vendor, 16, True), (f"Account Number: {fields['account_number']} - Page 2", 11, False)] + charges + summary)
    truth = _ground_truth(
        sample_id=sample_id,
        document_type="bill",
        document_subtype=subtype,
        category="core_bill",
        year=year,
        page_count=page_count,
        fields=fields,
        line_items=line_items,
        source_type="synthetic_controlled",
        source_provider="ReceiptSift locally generated controlled fixture",
        source_url=None,
        ground_truth_status="exact",
        authenticity_status="synthetic not a real transaction",
        state=state,
        pdf_type="image_only" if image_only else "searchable_text",
        core_bill=True,
    )
    return truth, pages


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _manifest_row(truth: dict[str, Any], relative_folder: str, document_path: Path, group: str) -> dict[str, Any]:
    return {
        "sample_id": truth["sample_id"],
        "group": group,
        "document_type": truth["document_type"],
        "document_subtype": truth["document_subtype"],
        "category": truth["category"],
        "document_year": truth["document"]["year"],
        "relative_folder": relative_folder.replace("\\", "/"),
        "page_count": truth["document"]["page_count"],
        "pdf_type": truth["document"]["pdf_type"],
        "source_type": truth["source"]["type"],
        "source_provider": truth["source"]["provider"],
        "source_url": truth["source"]["url"] or "",
        "ground_truth_status": truth["source"]["ground_truth_status"],
        "authenticity_status": truth["source"]["authenticity_status"],
        "core_bill": "yes" if truth["features"]["core_bill"] else "no",
        "sha256": _sha256(document_path),
    }


def build(source: Path, output: Path) -> None:
    if output.exists():
        raise SystemExit(f"Output already exists: {output}")
    output.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    truths: list[dict[str, Any]] = []
    source_manifest = {row["sample_id"]: row for row in csv.DictReader((source / "manifest.csv").open(encoding="utf-8-sig"))}

    existing_root = output / "01_现有Receipt与历史兼容样本200份"
    for expected_path in sorted(source.rglob("expected.json")):
        raw = json.loads(expected_path.read_text(encoding="utf-8"))
        sample_id = raw["sample_id"]
        row = source_manifest[sample_id]
        truth = _migrate_legacy_expected(raw, row)
        target = existing_root / sample_id
        target.mkdir(parents=True)
        images = sorted(
            path
            for path in expected_path.parent.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"} and "pipeline_preview" not in path.name
        )
        if not images:
            raise RuntimeError(f"No source image found for {sample_id}")
        document_path = target / "document.pdf"
        _images_to_pdf(images, document_path)
        shutil.copy2(images[0], target / f"preview{images[0].suffix.lower()}")
        _write_json(target / "ground_truth.v1.json", truth)
        relative = target.relative_to(output).as_posix()
        rows.append(_manifest_row(truth, relative, document_path, "existing_200_schema_migration"))
        truths.append(truth)

    rng = random.Random(20260824)
    invoice_root = output / "02_现代美国Invoice补充50份"
    for index in range(1, 51):
        truth, pages = _invoice_fixture(index, rng)
        target = invoice_root / truth["sample_id"]
        target.mkdir(parents=True)
        document_path = target / "document.pdf"
        _write_pdf(pages, document_path, truth["document"]["pdf_type"] == "image_only")
        _render_preview(document_path, target / "preview.jpg")
        _write_json(target / "ground_truth.v1.json", truth)
        relative = target.relative_to(output).as_posix()
        rows.append(_manifest_row(truth, relative, document_path, "invoice_supplement_50"))
        truths.append(truth)

    bill_root = output / "03_现代美国核心Bill补充25份"
    for index in range(1, 26):
        truth, pages = _bill_fixture(index, rng)
        target = bill_root / truth["sample_id"]
        target.mkdir(parents=True)
        document_path = target / "document.pdf"
        _write_pdf(pages, document_path, truth["document"]["pdf_type"] == "image_only")
        _render_preview(document_path, target / "preview.jpg")
        _write_json(target / "ground_truth.v1.json", truth)
        relative = target.relative_to(output).as_posix()
        rows.append(_manifest_row(truth, relative, document_path, "core_bill_supplement_25"))
        truths.append(truth)

    fieldnames = list(rows[0])
    with (output / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    with (output / "manifest.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (output / "ground_truth_schema_v1.jsonl").open("w", encoding="utf-8") as handle:
        for truth in truths:
            handle.write(json.dumps(truth, ensure_ascii=False) + "\n")
    _contact_sheet(output)

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://receiptsift.example/schemas/financial-document-ground-truth-v1.json",
        "title": "ReceiptSift Financial Document Ground Truth",
        "type": "object",
        "required": ["schema_version", "sample_id", "document_type", "source", "document", "fields", "line_items"],
        "properties": {
            "schema_version": {"const": "1.0"},
            "sample_id": {"type": "string"},
            "document_type": {"enum": ["receipt", "invoice", "bill"]},
            "document_subtype": {"type": ["string", "null"]},
            "source": {"type": "object"},
            "document": {"type": "object"},
            "fields": {"type": "object", "required": list(ALL_FIELDS)},
            "line_items": {"type": "array"},
        },
    }
    _write_json(output / "schema_v1.json", schema)

    (output / "README.md").write_text(
        "# 美国财务文档验收集 275 份（Schema v1，2020-2026）\n\n"
        "组成：现有200份迁移数据 + 50份现代受控合成Invoice + 25份现代受控合成核心Bill。\n\n"
        "- 所有样本均为普通文件夹，每份含 `document.pdf`、`preview.jpg/png` 和 `ground_truth.v1.json`。\n"
        "- 受控合成文件均有 `SYNTHETIC TEST DOCUMENT - NOT VALID` 水印，不是真实交易凭证。\n"
        "- 39份美国官方公开页面只做流程测试，不计字段准确率。\n"
        "- 原数据中40份Receipt风格的Bill保留作兼容样本，但不计作新增核心Bill。\n"
        "- 先看 `COVERAGE_REPORT.md`、`SOURCES_AND_VERIFICATION.md`、`schema_v1.json` 和 `manifest.csv`。\n",
        encoding="utf-8",
    )
    (output / "SOURCES_AND_VERIFICATION.md").write_text(
        "# 来源与真实性说明\n\n"
        "## 现有200份\n\n"
        "沿用原始数据来源和SHA-256记录。其中39份来自 Oak Ridge National Laboratory / "
        "U.S. Department of Energy Better Plants 与 City of Tampa 的公开样例或指南页；"
        "161份为受控合成测试单据。逐份来源见 `manifest.csv`。\n\n"
        "## 新增50份Invoice和25份核心Bill\n\n"
        "全部由 ReceiptSift 在本地生成，时间范围为2020-2026，使用虚构公司、客户、账户、税号和金额。"
        "它们不是公开下载的真实交易，也不得被描述为真实客户文件。"
        "每份均带不可误认的无效测试水印，并有精确字段真值。\n\n"
        "这样设计的目的，是在不收集私人财务信息的前提下，稳定测试Invoice/Bill字段、金额勾稽、单页/多页及可复制/扫描PDF路由。\n",
        encoding="utf-8",
    )

    counts: dict[str, int] = {}
    for row in rows:
        key = row["document_type"]
        counts[key] = counts.get(key, 0) + 1
    exact = sum(row["ground_truth_status"] == "exact" for row in rows)
    multipage = sum(int(row["page_count"]) > 1 for row in rows)
    image_only = sum(row["pdf_type"] == "image_only" for row in rows)
    (output / "COVERAGE_REPORT.md").write_text(
        "# 覆盖报告\n\n"
        f"- 文档：{len(rows)}份\n"
        f"- 字段真值：{exact}份 exact，{len(rows) - exact}份 flow_only\n"
        f"- document_type：{json.dumps(counts, ensure_ascii=False)}\n"
        "- 新增合格Invoice：50份\n"
        "- 新增核心Bill：25份（utility、telecom、credit_card_statement）\n"
        f"- 多页文档：{multipage}份\n"
        f"- image-only扫描型PDF：{image_only}份\n"
        f"- searchable-text可复制PDF：{len(rows) - image_only}份\n"
        "- 年份：2020-2026\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "documents": len(rows), "exact": exact, "types": counts}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
