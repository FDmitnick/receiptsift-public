from __future__ import annotations

import importlib.util
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from statistics import mean
from typing import Any

from .document_schema import classify_document_type, finalize_document_result

MONEY_RE = re.compile(r"(?<![\w.])(?:USD|CNY|RMB|EUR|GBP|JPY|[$¥￥€£])?\s*(-?\d[\d,]*\.\d{2})(?!\d)", re.I)
DATE_PATTERNS = [
    re.compile(r"(?P<y>20\d{2})[-/.年](?P<m>1[0-2]|0?[1-9])[-/.月](?P<d>3[01]|[12]\d|0?[1-9])日?"),
    re.compile(r"(?P<m>1[0-2]|0?[1-9])[-/.](?P<d>3[01]|[12]\d|0?[1-9])[-/.](?P<y>20\d{2})"),
]

TOTAL_LABELS = ("grand total", "amount due", "balance due", "total", "合计", "总计", "应付", "实付", "金额")
SUBTOTAL_LABELS = ("subtotal", "sub-total", "小计", "商品合计")
TAX_LABELS = ("tax", "vat", "gst", "sales tax", "service fee", "税", "服务费", "附加费")
TIP_LABELS = ("tip", "gratuity", "小费")
PAYMENT_LABELS = ("payment", "paid by", "tender", "支付方式", "付款方式")
NUMBER_LABELS = ("receipt no", "receipt #", "invoice no", "invoice #", "order no", "no.", "收据编号", "发票号码", "订单号", "单号")
DUE_DATE_LABELS = ("due date", "payment due", "pay by", "到期日", "付款截止")
ACCOUNT_NUMBER_LABELS = ("account number", "account no", "account #", "acct no", "账号", "账户")
PURCHASE_ORDER_LABELS = ("purchase order", "po number", "po #", "采购订单")
SHIPPING_LABELS = ("shipping", "freight", "delivery", "运费")
FEE_LABELS = ("fee", "fees", "service charge", "手续费")
AMOUNT_PAID_LABELS = ("amount paid", "paid amount", "已支付")
BALANCE_DUE_LABELS = ("balance due", "amount due", "total due", "应付余额", "应付金额")
PREVIOUS_BALANCE_LABELS = ("previous balance", "prior balance", "上期余额")
PAYMENTS_LABELS = ("payments received", "payments", "payment received", "已付款")
CREDITS_LABELS = ("credits", "credit applied", "抵扣")
ADJUSTMENTS_LABELS = ("adjustments", "adjustment", "调整")
CURRENT_CHARGES_LABELS = ("current charges", "new charges", "本期费用")
LATE_FEE_LABELS = ("late fee", "late charge", "滞纳金")
MINIMUM_DUE_LABELS = ("minimum due", "minimum payment", "最低还款")
DISCOUNT_LABELS = ("discount", "discounts", "折扣")
REFUND_LABELS = ("refund amount", "refund", "退款")
PAYMENT_TERMS_LABELS = ("payment terms", "terms", "付款条款")
ORIGINAL_INVOICE_LABELS = ("original invoice", "original invoice number", "原发票")


class PdfParseError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


ACTIVE_PDF_OBJECT_RE = re.compile(
    r"/(?:JavaScript|JS|Launch|RichMedia|SubmitForm|ImportData|EmbeddedFile|OpenAction|AA)\b"
)


@dataclass
class TextLine:
    page: int
    text: str
    bbox: list[float]
    confidence: float
    method: str

    def source(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "bbox": [round(value, 5) for value in self.bbox],
            "text": self.text,
        }


def ocr_available() -> bool:
    return bool(importlib.util.find_spec("rapidocr") and importlib.util.find_spec("onnxruntime"))


@lru_cache(maxsize=1)
def _ocr_engine():
    from rapidocr import RapidOCR

    return RapidOCR()


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalized_bbox(bbox: Iterable[float], width: float, height: float) -> list[float]:
    x0, y0, x1, y1 = bbox
    return [
        max(0.0, min(1.0, x0 / width)),
        max(0.0, min(1.0, y0 / height)),
        max(0.0, min(1.0, x1 / width)),
        max(0.0, min(1.0, y1 / height)),
    ]


def _embedded_lines(page: Any, page_number: int) -> list[TextLine]:
    result: list[TextLine] = []
    data = page.get_text("dict", sort=True)
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = _normalize_space("".join(span.get("text", "") for span in spans))
            if not text:
                continue
            bbox = line.get("bbox") or block.get("bbox")
            result.append(
                TextLine(
                    page=page_number,
                    text=text,
                    bbox=_normalized_bbox(bbox, page.rect.width, page.rect.height),
                    confidence=0.99,
                    method="embedded_text",
                )
            )
    return result


def _safe_render_scale(page: Any, desired_scale: float, max_render_dimension: int) -> float:
    longest_side = max(float(page.rect.width), float(page.rect.height), 1.0)
    return max(0.05, min(desired_scale, max(int(max_render_dimension), 256) / longest_side))


def _ocr_lines(page: Any, page_number: int, max_render_dimension: int = 3000) -> list[TextLine]:
    if not ocr_available():
        return []
    import numpy as np
    import pymupdf

    scale = _safe_render_scale(page, 2.2, max_render_dimension)
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, pixmap.n)
    output = _ocr_engine()(image)
    if output is None or output.boxes is None:
        return []

    fragments: list[tuple[float, float, float, float, str, float]] = []
    for box, text, score in zip(output.boxes, output.txts, output.scores, strict=True):
        x_values = [float(point[0]) for point in box]
        y_values = [float(point[1]) for point in box]
        fragments.append((min(x_values), min(y_values), max(x_values), max(y_values), _normalize_space(text), float(score)))
    fragments.sort(key=lambda item: (item[1], item[0]))

    grouped: list[list[tuple[float, float, float, float, str, float]]] = []
    for fragment in fragments:
        center_y = (fragment[1] + fragment[3]) / 2
        if grouped:
            previous = grouped[-1]
            previous_y = mean((item[1] + item[3]) / 2 for item in previous)
            tolerance = max(8.0, mean(item[3] - item[1] for item in previous) * 0.65)
            if abs(center_y - previous_y) <= tolerance:
                previous.append(fragment)
                previous.sort(key=lambda item: item[0])
                continue
        grouped.append([fragment])

    lines: list[TextLine] = []
    for group in grouped:
        text = _normalize_space(" ".join(item[4] for item in group))
        if not text:
            continue
        bbox = [
            min(item[0] for item in group),
            min(item[1] for item in group),
            max(item[2] for item in group),
            max(item[3] for item in group),
        ]
        lines.append(
            TextLine(
                page=page_number,
                text=text,
                bbox=_normalized_bbox(bbox, pixmap.width, pixmap.height),
                confidence=mean(item[5] for item in group),
                method="ocr",
            )
        )
    return lines


def _source_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.translate(str.maketrans({"−": "-", "–": "-", "—": "-", "‐": "-"}))
    return _normalize_space(text)


def _source_tokens(value: str) -> list[str]:
    return re.findall(r"[\w]+", value, flags=re.UNICODE)


def _source_match_score(evidence: str, candidate: str) -> float:
    expected = _source_text(evidence)
    observed = _source_text(candidate)
    if not expected or not observed:
        return 0.0
    if expected == observed:
        return 1.0
    if expected in observed or observed in expected:
        coverage = min(len(expected), len(observed)) / max(len(expected), len(observed))
        return 0.88 + (0.12 * coverage)

    expected_tokens = _source_tokens(expected)
    observed_tokens = _source_tokens(observed)
    if not expected_tokens or not observed_tokens:
        return SequenceMatcher(None, expected, observed).ratio()
    expected_set = set(expected_tokens)
    observed_set = set(observed_tokens)
    overlap = len(expected_set & observed_set)
    token_score = (0.72 * overlap / len(expected_set)) + (0.28 * overlap / len(observed_set))
    return max(token_score, SequenceMatcher(None, expected, observed).ratio())


def _merged_line_source(lines: list[TextLine]) -> dict[str, Any]:
    return {
        "page": lines[0].page,
        "bbox": [
            round(min(line.bbox[0] for line in lines), 5),
            round(min(line.bbox[1] for line in lines), 5),
            round(max(line.bbox[2] for line in lines), 5),
            round(max(line.bbox[3] for line in lines), 5),
        ],
        "text": " ".join(line.text for line in lines),
    }


def _locate_evidence(evidence: str, lines: list[TextLine]) -> dict[str, Any] | None:
    expected = _source_text(evidence)
    if not expected or not lines:
        return None

    candidates: list[tuple[float, list[TextLine]]] = []
    for start in range(len(lines)):
        for length in range(1, min(3, len(lines) - start) + 1):
            group = lines[start : start + length]
            candidate_text = " ".join(line.text for line in group)
            candidates.append((_source_match_score(expected, candidate_text), group))
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_group = candidates[0]
    if best_score < 0.68:
        return None

    # A bare value can occur repeatedly on a statement. In that case, declining
    # to draw a box is safer than pointing the reviewer at the wrong occurrence.
    has_label = bool(re.search(r"[^\W\d_]", expected, flags=re.UNICODE))
    if not has_label:
        equally_likely = [group for score, group in candidates[1:] if score >= best_score - 0.02]
        if equally_likely:
            return None
    return _merged_line_source(best_group)


def locate_result_sources(
    pdf_bytes: bytes,
    result: dict[str, Any],
    *,
    max_render_dimension: int = 3000,
) -> int:
    """Fill missing field evidence boxes from retained PDF text or local OCR."""

    pending_by_page: dict[int, list[dict[str, Any]]] = {}
    fields = result.get("fields") if isinstance(result.get("fields"), dict) else {}
    records = list(fields.values())
    records.extend(result.get("items") if isinstance(result.get("items"), list) else [])
    for record in records:
        if not isinstance(record, dict):
            continue
        source = record.get("source") if isinstance(record.get("source"), dict) else None
        existing_bbox = source.get("bbox") if source else None
        if (
            not source
            or (isinstance(existing_bbox, list) and len(existing_bbox) == 4)
            or not str(source.get("text") or "").strip()
        ):
            continue
        try:
            page_number = int(source.get("page"))
        except (TypeError, ValueError):
            continue
        if page_number >= 1:
            pending_by_page.setdefault(page_number, []).append(source)
    if not pending_by_page:
        return 0

    try:
        import pymupdf

        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        return 0

    located_count = 0
    try:
        for page_number, sources in pending_by_page.items():
            if page_number > document.page_count:
                continue
            page = document.load_page(page_number - 1)
            try:
                embedded_lines = _embedded_lines(page, page_number)
            except Exception:
                embedded_lines = []
            unmatched: list[dict[str, Any]] = []
            for source in sources:
                located = _locate_evidence(str(source.get("text") or ""), embedded_lines)
                if located is None:
                    unmatched.append(source)
                    continue
                source["bbox"] = located["bbox"]
                located_count += 1

            if unmatched and ocr_available():
                try:
                    ocr_lines = _ocr_lines(page, page_number, max_render_dimension)
                except Exception:
                    ocr_lines = []
                for source in unmatched:
                    located = _locate_evidence(str(source.get("text") or ""), ocr_lines)
                    if located is not None:
                        source["bbox"] = located["bbox"]
                        located_count += 1
    finally:
        document.close()
    return located_count


def _contains(text: str, labels: Iterable[str]) -> bool:
    lowered = text.casefold()
    return any(label.casefold() in lowered for label in labels)


def _contains_label(text: str, labels: Iterable[str]) -> bool:
    return any(
        re.search(rf"(?<!\w){re.escape(label)}(?!\w)", text, re.I)
        for label in labels
    )


def _money_values(text: str) -> list[float]:
    values: list[float] = []
    for match in MONEY_RE.finditer(text):
        try:
            values.append(round(float(match.group(1).replace(",", "")), 2))
        except ValueError:
            continue
    return values


def _find_labeled_amount(
    lines: list[TextLine], labels: Iterable[str], excluded: Iterable[str] = ()
) -> tuple[float | None, TextLine | None]:
    candidates: list[tuple[float, TextLine]] = []
    for line in lines:
        if _contains_label(line.text, labels) and not _contains_label(line.text, excluded):
            amounts = _money_values(line.text)
            value_line = line
            if not amounts:
                value_line = _nearby_value_line(lines, line, prefer_same_row=True)
                amounts = _money_values(value_line.text) if value_line else []
            if amounts:
                candidates.append((amounts[-1], value_line))
    return candidates[-1] if candidates else (None, None)


def _center_y(line: TextLine) -> float:
    return (line.bbox[1] + line.bbox[3]) / 2


def _nearby_value_line(
    lines: list[TextLine], label_line: TextLine, *, prefer_same_row: bool = False
) -> TextLine | None:
    same_row = [
        line
        for line in lines
        if line is not label_line
        and line.page == label_line.page
        and line.bbox[0] > label_line.bbox[0]
        and abs(_center_y(line) - _center_y(label_line)) <= 0.009
    ]
    if prefer_same_row and same_row:
        return min(same_row, key=lambda line: line.bbox[0])
    if prefer_same_row:
        return None
    below = [
        line
        for line in lines
        if line is not label_line
        and line.page == label_line.page
        and 0 <= line.bbox[1] - label_line.bbox[3] <= 0.035
        and abs(line.bbox[0] - label_line.bbox[0]) <= 0.08
    ]
    if below:
        return min(below, key=lambda line: (line.bbox[1], abs(line.bbox[0] - label_line.bbox[0])))
    return min(same_row, key=lambda line: line.bbox[0]) if same_row else None


def _find_date(lines: list[TextLine]) -> tuple[str | None, TextLine | None]:
    for line in lines:
        for pattern in DATE_PATTERNS:
            match = pattern.search(line.text)
            if not match:
                continue
            try:
                parsed = datetime(int(match.group("y")), int(match.group("m")), int(match.group("d")))
            except ValueError:
                continue
            return parsed.strftime("%Y-%m-%d"), line
    return None, None


def _find_labeled_date(lines: list[TextLine], labels: Iterable[str]) -> tuple[str | None, TextLine | None]:
    labeled = [line for line in lines if _contains(line.text, labels)]
    direct = _find_date(labeled)
    if direct[0] is not None:
        return direct
    for label_line in labeled:
        value_line = _nearby_value_line(lines, label_line)
        if value_line:
            value = _find_date([value_line])
            if value[0] is not None:
                return value
    return None, None


def _find_labeled_identifier(lines: list[TextLine], labels: Iterable[str]) -> tuple[str | None, TextLine | None]:
    for line in lines:
        if not _contains(line.text, labels):
            continue
        value = re.split(r"[:：#]", line.text, maxsplit=1)[-1].strip()
        value = re.sub(r"^(?:no\.?|number)\s*", "", value, flags=re.I).strip(" -")
        if value and value.casefold() != line.text.casefold() and len(value) <= 128:
            return value, line
        value_line = _nearby_value_line(lines, line)
        if value_line and len(value_line.text.strip()) <= 128:
            return value_line.text.strip(), value_line
    return None, None


def _find_labeled_text(lines: list[TextLine], labels: Iterable[str], max_length: int = 256) -> tuple[str | None, TextLine | None]:
    for line in lines:
        if not _contains(line.text, labels):
            continue
        parts = re.split(r"[:：]", line.text, maxsplit=1)
        if len(parts) == 2 and parts[1].strip():
            return parts[1].strip()[:max_length], line
        value_line = _nearby_value_line(lines, line)
        if value_line and value_line.text.strip():
            return value_line.text.strip()[:max_length], value_line
    return None, None


def _find_party(lines: list[TextLine], label: str) -> tuple[str | None, TextLine | None, str | None, TextLine | None]:
    inline_pattern = re.compile(rf"^\s*{re.escape(label)}\s*[:：-]\s*(?P<value>.+?)\s*$", re.I)
    inline = next(((line, match) for line in lines if (match := inline_pattern.match(line.text))), None)
    if inline is not None:
        name_line, match = inline
        address_candidates = [
            line
            for line in lines
            if line.page == name_line.page
            and 0 < line.bbox[1] - name_line.bbox[3] <= 0.04
            and abs(line.bbox[0] - name_line.bbox[0]) <= 0.05
            and line.text.strip()
            and "synthetic test data" not in line.text.casefold()
        ]
        address_line = min(address_candidates, key=lambda line: line.bbox[1]) if address_candidates else None
        return (
            match.group("value").strip(),
            name_line,
            address_line.text.strip() if address_line else None,
            address_line,
        )

    heading = next((line for line in lines if line.text.strip().casefold() == label.casefold()), None)
    if heading is None:
        return None, None, None, None
    candidates = [
        line
        for line in lines
        if line.page == heading.page
        and 0 < line.bbox[1] - heading.bbox[3] <= 0.085
        and abs(line.bbox[0] - heading.bbox[0]) <= 0.05
        and line.text.strip()
        and "synthetic test data" not in line.text.casefold()
    ]
    candidates.sort(key=lambda line: line.bbox[1])
    name_line = candidates[0] if candidates else None
    address_line = candidates[1] if len(candidates) > 1 else None
    return (
        name_line.text.strip() if name_line else None,
        name_line,
        address_line.text.strip() if address_line else None,
        address_line,
    )


def _find_vendor_address(lines: list[TextLine]) -> tuple[str | None, TextLine | None]:
    address_re = re.compile(r"\b(?:street|st\.?|avenue|ave\.?|road|rd\.?|boulevard|blvd\.?|drive|dr\.?)\b", re.I)
    for line in lines[:15]:
        if address_re.search(line.text) and re.search(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b", line.text):
            return line.text.strip(), line
    return None, None


def _find_tax_id(lines: list[TextLine]) -> tuple[str | None, TextLine | None]:
    pattern = re.compile(r"\b(?:tax\s*id|ein|vat\s*id)\b\s*[:#-]?\s*[A-Z0-9]", re.I)
    for line in lines:
        value = line.text.strip()
        if pattern.search(value) and len(value) <= 128:
            return value, line
    return _find_labeled_identifier(lines, ("tax id", "ein", "vat id"))


def _find_receipt_number(lines: list[TextLine]) -> tuple[str | None, TextLine | None]:
    for line in lines:
        if not _contains(line.text, NUMBER_LABELS):
            continue
        match = re.search(r"(?:no\.?|#|编号|号码|单号)\s*[:：#-]?\s*([A-Z0-9][A-Z0-9-]{2,})", line.text, re.I)
        if match:
            return match.group(1), line
    return None, None


def _find_payment(lines: list[TextLine]) -> tuple[str | None, TextLine | None]:
    known = ("visa", "mastercard", "amex", "cash", "alipay", "wechat", "paypal", "现金", "支付宝", "微信", "银行卡")
    for line in lines:
        lowered = line.text.casefold()
        if any(label in lowered for label in ("payment terms", "amount paid", "payments", "minimum payment")):
            continue
        if _contains(line.text, PAYMENT_LABELS) or _contains(line.text, known):
            for method in known:
                if method.casefold() in line.text.casefold():
                    return method.upper() if method in {"visa", "mastercard", "amex"} else method.title(), line
            value = re.split(r"[:：]", line.text, maxsplit=1)
            return (value[-1].strip() if value else line.text), line
    return None, None


def _currency(lines: list[TextLine]) -> tuple[str, TextLine | None]:
    for line in lines:
        text = line.text.upper()
        if "EUR" in text or "€" in text:
            return "EUR", line
        if "GBP" in text or "£" in text:
            return "GBP", line
        if "JPY" in text or "円" in text:
            return "JPY", line
        if "CNY" in text or "RMB" in text or "人民币" in text or "元" in text or "￥" in text:
            return "CNY", line
        if "USD" in text or "$" in text:
            return "USD", line
    return "USD", None


def _merchant(lines: list[TextLine]) -> tuple[str | None, TextLine | None]:
    skip = (
        TOTAL_LABELS
        + SUBTOTAL_LABELS
        + TAX_LABELS
        + TIP_LABELS
        + PAYMENT_LABELS
        + NUMBER_LABELS
        + ("receipt", "invoice", "date", "time", "tel", "phone", "address", "thank", "收据", "发票", "日期", "电话", "地址", "谢谢")
    )
    for line in lines[:15]:
        text = line.text.strip(" -*_=|:")
        if len(text) < 2 or len(text) > 90 or _contains(text, skip):
            continue
        if _money_values(text) or re.fullmatch(r"[\d\W_]+", text):
            continue
        digit_ratio = sum(character.isdigit() for character in text) / max(len(text), 1)
        if digit_ratio < 0.3:
            return text, line
    return None, None


def _table_header_x(headers: list[TextLine], *names: str) -> float | None:
    matches = [line for line in headers if line.text.strip().casefold() in names]
    return matches[-1].bbox[0] if matches else None


def _nearest_table_cell(lines: list[TextLine], x: float | None, predicate) -> TextLine | None:
    if x is None:
        return None
    matches = [line for line in lines if predicate(line)]
    return min(matches, key=lambda line: abs(line.bbox[0] - x)) if matches else None


def _line_items(lines: list[TextLine]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    sku_lines = [line for line in lines if re.fullmatch(r"SKU-[A-Z0-9-]+", line.text.strip(), re.I)]
    for sku_line in sku_lines:
        row = sorted(
            [
                line
                for line in lines
                if line.page == sku_line.page and abs(_center_y(line) - _center_y(sku_line)) <= 0.006
            ],
            key=lambda line: line.bbox[0],
        )
        page_headers = [
            line
            for line in lines
            if line.page == sku_line.page and line.bbox[1] < sku_line.bbox[1]
        ]

        description_line = _nearest_table_cell(
            row,
            _table_header_x(page_headers, "description"),
            lambda line, current_sku=sku_line: not _money_values(line.text) and line is not current_sku,
        )
        qty_line = _nearest_table_cell(
            row, _table_header_x(page_headers, "qty", "quantity"), lambda line: bool(re.fullmatch(r"\d+(?:\.\d+)?", line.text))
        )
        unit_line = _nearest_table_cell(
            row, _table_header_x(page_headers, "unit"), lambda line: bool(re.fullmatch(r"[A-Z]{1,8}", line.text))
        )
        price_line = _nearest_table_cell(
            row, _table_header_x(page_headers, "price", "unit price"), lambda line: bool(_money_values(line.text))
        )
        rate_line = _nearest_table_cell(row, _table_header_x(page_headers, "tax %", "tax rate"), lambda line: "%" in line.text)
        tax_line = _nearest_table_cell(row, _table_header_x(page_headers, "tax"), lambda line: bool(_money_values(line.text)))
        amount_line = _nearest_table_cell(
            row, _table_header_x(page_headers, "amount", "line amount"), lambda line: bool(_money_values(line.text))
        )
        amount_lines = [amount_line] if amount_line else []
        if not description_line or not qty_line or not unit_line or not price_line or not amount_lines:
            continue
        quantity = float(qty_line.text)
        unit_price = _money_values(price_line.text)[-1]
        amount = _money_values(amount_lines[-1].text)[-1]
        tax_amount = _money_values(tax_line.text)[-1] if tax_line else None
        rate_values = re.findall(r"-?\d+(?:\.\d+)?", rate_line.text) if rate_line else []
        tax_rate = round(float(rate_values[-1]) / 100, 6) if rate_values else None
        discount = round(quantity * unit_price - abs(amount), 2)
        if amount < 0:
            discount = -discount
        if abs(discount) <= 0.02:
            discount = 0.0
        items.append(
            {
                "description": description_line.text.strip(),
                "sku": sku_line.text.strip(),
                "quantity": quantity,
                "unit": unit_line.text.strip(),
                "unit_price": unit_price,
                "discount": discount,
                "tax_rate": tax_rate,
                "tax_amount": tax_amount,
                "amount": amount,
                "line_total": round(amount + (tax_amount or 0.0), 2),
                "confidence": round(min(line.confidence for line in row) * 0.96, 3),
                "source": sku_line.source(),
            }
        )
    if items:
        return items[:200]
    skip_labels = (
        TOTAL_LABELS
        + SUBTOTAL_LABELS
        + TAX_LABELS
        + TIP_LABELS
        + PAYMENT_LABELS
        + NUMBER_LABELS
        + SHIPPING_LABELS
        + FEE_LABELS
        + AMOUNT_PAID_LABELS
        + BALANCE_DUE_LABELS
        + DISCOUNT_LABELS
        + REFUND_LABELS
        + ("receipt", "invoice", "date", "time", "address", "tel", "phone", "thank", "收据", "发票", "日期", "电话", "地址", "谢谢")
    )
    qty_pattern = re.compile(
        r"^(?P<name>.+?)\s+(?P<qty>\d+(?:\.\d+)?)\s*(?:x|×|@)\s*(?P<unit>\d[\d,]*\.\d{2})\s+(?P<amount>\d[\d,]*\.\d{2})$", re.I
    )
    simple_pattern = re.compile(r"^(?P<name>.+?\D)\s+(?P<amount>\d[\d,]*\.\d{2})$")
    for line in lines:
        if sku_lines and any(line.page == sku.page and abs(_center_y(line) - _center_y(sku)) <= 0.006 for sku in sku_lines):
            continue
        text = line.text.strip()
        if re.fullmatch(r"(?:USD|EUR|GBP|JPY|CNY|RMB)\s+-?\d[\d,]*\.\d{2}", text, re.I):
            continue
        if _contains_label(text, skip_labels):
            continue
        match = qty_pattern.match(text)
        if match:
            name = match.group("name").strip(" .:-")
            if len(name) >= 2:
                quantity = float(match.group("qty"))
                unit_price = float(match.group("unit").replace(",", ""))
                amount = float(match.group("amount").replace(",", ""))
                discount = round(quantity * unit_price - abs(amount), 2)
                if amount < 0:
                    discount = -discount
                if abs(discount) <= 0.02:
                    discount = 0.0
                items.append(
                    {
                        "description": name,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "discount": discount,
                        "amount": amount,
                        "confidence": round(line.confidence * 0.96, 3),
                        "source": line.source(),
                    }
                )
                continue
        match = simple_pattern.match(text)
        if match:
            name = match.group("name").strip(" .:-")
            if len(name) >= 2 and not re.search(r"\b(?:street|road|st\.?|ave\.?|phone)\b", name, re.I):
                items.append(
                    {
                        "description": name,
                        "quantity": 1.0,
                        "unit_price": None,
                        "amount": float(match.group("amount").replace(",", "")),
                        "confidence": round(line.confidence * 0.82, 3),
                        "source": line.source(),
                    }
                )
    return items[:200]


def _field(value: Any, line: TextLine | None, confidence: float) -> dict[str, Any]:
    return {
        "value": value,
        "confidence": round(min(confidence, line.confidence if line else confidence), 3) if value is not None else 0.0,
        "source": line.source() if line else None,
    }


def validate_pdf_security(
    document: Any,
    *,
    max_xref_objects: int = 50_000,
    max_page_dimension: float = 14_400,
) -> None:
    """Reject high-risk or unbounded PDF structures before text/OCR processing."""
    xref_count = int(document.xref_length())
    if xref_count > max(int(max_xref_objects), 1):
        raise PdfParseError(
            "pdf_too_complex",
            f"The PDF contains {xref_count} objects; the safety limit is {max_xref_objects}.",
        )
    try:
        embedded_count = int(document.embfile_count())
    except Exception:
        embedded_count = 0
    if embedded_count:
        raise PdfParseError("active_pdf_content", "PDFs containing embedded files are not accepted.")
    dimension_limit = max(float(max_page_dimension), 72.0)
    for page in document:
        if max(float(page.rect.width), float(page.rect.height)) > dimension_limit:
            raise PdfParseError(
                "page_dimensions_exceeded",
                f"A PDF page exceeds the safety dimension limit of {dimension_limit:g} points.",
            )
    for xref in range(1, xref_count):
        try:
            object_source = document.xref_object(xref, compressed=True)
        except Exception:
            continue
        if ACTIVE_PDF_OBJECT_RE.search(object_source):
            raise PdfParseError(
                "active_pdf_content",
                "PDFs containing scripts, launch actions, rich media, forms that submit data, or embedded files are not accepted.",
            )


def pdf_page_count(
    pdf_bytes: bytes,
    *,
    max_xref_objects: int = 50_000,
    max_page_dimension: float = 14_400,
) -> int:
    """Read only the PDF envelope so plan limits can be enforced before OCR."""
    try:
        import pymupdf
    except ImportError as error:
        raise RuntimeError("PyMuPDF is required. Install the packages in requirements.txt.") from error

    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise PdfParseError("invalid_pdf", "The uploaded file is not a readable PDF.") from error
    try:
        if document.needs_pass:
            raise PdfParseError("encrypted_pdf", "Password-protected PDFs are not supported.")
        if document.page_count < 1:
            raise PdfParseError("empty_pdf", "The PDF does not contain any pages.")
        validate_pdf_security(
            document,
            max_xref_objects=max_xref_objects,
            max_page_dimension=max_page_dimension,
        )
        return int(document.page_count)
    finally:
        document.close()


def parse_pdf(
    pdf_bytes: bytes,
    max_pages: int = 30,
    *,
    max_xref_objects: int = 50_000,
    max_page_dimension: float = 14_400,
    max_render_dimension: int = 3000,
) -> tuple[dict[str, Any], bytes | None]:
    try:
        import pymupdf
    except ImportError as error:
        raise RuntimeError("PyMuPDF is required. Install the packages in requirements.txt.") from error

    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise PdfParseError("invalid_pdf", "The uploaded file is not a readable PDF.") from error

    try:
        if document.needs_pass:
            raise PdfParseError("encrypted_pdf", "Password-protected PDFs are not supported.")
        if document.page_count < 1:
            raise PdfParseError("empty_pdf", "The PDF does not contain any pages.")
        if document.page_count > max_pages:
            raise PdfParseError("too_many_pages", f"The PDF has {document.page_count} pages; the limit is {max_pages}.")
        validate_pdf_security(
            document,
            max_xref_objects=max_xref_objects,
            max_page_dimension=max_page_dimension,
        )

        all_lines: list[TextLine] = []
        page_texts: list[dict[str, Any]] = []
        methods: list[str] = []
        preview: bytes | None = None
        ocr_missing = False

        for index, page in enumerate(document):
            if index == 0:
                preview_scale = _safe_render_scale(page, 1.7, max_render_dimension)
                preview = page.get_pixmap(
                    matrix=pymupdf.Matrix(preview_scale, preview_scale), alpha=False
                ).tobytes("png")
            lines = _embedded_lines(page, index + 1)
            embedded_character_count = sum(len(line.text) for line in lines)
            if embedded_character_count < 20:
                ocr_lines = _ocr_lines(page, index + 1, max_render_dimension)
                if ocr_lines:
                    lines = ocr_lines
                else:
                    ocr_missing = True
            method = lines[0].method if lines else "none"
            methods.append(method)
            all_lines.extend(lines)
            page_texts.append({"page": index + 1, "text": "\n".join(line.text for line in lines), "method": method})

        combined_text = "\n".join(line.text for line in all_lines)
        document_type = classify_document_type(combined_text)
        merchant, merchant_line = _merchant(all_lines)
        vendor_address, vendor_address_line = _find_vendor_address(all_lines)
        vendor_tax_id, vendor_tax_id_line = _find_tax_id(all_lines)
        bill_to_name, bill_to_name_line, bill_to_address, bill_to_address_line = _find_party(all_lines, "BILL TO")
        ship_to_name, ship_to_name_line, ship_to_address, ship_to_address_line = _find_party(all_lines, "SHIP TO")
        date, date_line = _find_date(all_lines)
        due_date, due_date_line = _find_labeled_date(all_lines, DUE_DATE_LABELS)
        currency, currency_line = _currency(all_lines)
        receipt_number, number_line = _find_receipt_number(all_lines)
        account_number, account_line = _find_labeled_identifier(all_lines, ACCOUNT_NUMBER_LABELS)
        purchase_order, purchase_order_line = _find_labeled_identifier(all_lines, PURCHASE_ORDER_LABELS)
        original_invoice, original_invoice_line = _find_labeled_identifier(all_lines, ORIGINAL_INVOICE_LABELS)
        payment_terms, payment_terms_line = _find_labeled_text(all_lines, PAYMENT_TERMS_LABELS)
        refund_method, _ = _find_labeled_text(all_lines, ("refund method",))
        subtotal, subtotal_line = _find_labeled_amount(all_lines, SUBTOTAL_LABELS)
        tax, tax_line = _find_labeled_amount(all_lines, TAX_LABELS)
        tip, tip_line = _find_labeled_amount(all_lines, TIP_LABELS)
        if document_type == "invoice":
            total, total_line = _find_labeled_amount(
                all_lines,
                ("invoice total", "grand total", "total"),
                SUBTOTAL_LABELS + BALANCE_DUE_LABELS,
            )
        else:
            total, total_line = _find_labeled_amount(all_lines, TOTAL_LABELS, SUBTOTAL_LABELS)
        shipping, shipping_line = _find_labeled_amount(all_lines, SHIPPING_LABELS)
        fees, fees_line = _find_labeled_amount(all_lines, FEE_LABELS, TAX_LABELS)
        amount_paid, amount_paid_line = _find_labeled_amount(all_lines, AMOUNT_PAID_LABELS)
        balance_due, balance_due_line = _find_labeled_amount(all_lines, BALANCE_DUE_LABELS)
        previous_balance, previous_balance_line = _find_labeled_amount(all_lines, PREVIOUS_BALANCE_LABELS)
        payments, payments_line = _find_labeled_amount(all_lines, PAYMENTS_LABELS)
        credits, credits_line = _find_labeled_amount(all_lines, CREDITS_LABELS)
        adjustments, adjustments_line = _find_labeled_amount(all_lines, ADJUSTMENTS_LABELS)
        current_charges, current_charges_line = _find_labeled_amount(all_lines, CURRENT_CHARGES_LABELS)
        late_fee, late_fee_line = _find_labeled_amount(all_lines, LATE_FEE_LABELS)
        minimum_due, minimum_due_line = _find_labeled_amount(all_lines, MINIMUM_DUE_LABELS)
        discount, discount_line = _find_labeled_amount(all_lines, DISCOUNT_LABELS)
        refund, refund_line = _find_labeled_amount(all_lines, REFUND_LABELS)
        payment, payment_line = _find_payment(all_lines)
        items = _line_items(all_lines)

        if discount is not None:
            discount = abs(discount)
        if refund is not None:
            refund = abs(refund)
        if document_type == "invoice" and amount_paid is not None:
            amount_paid = abs(amount_paid)
        if document_type == "invoice":
            fees = 0.0 if fees is None else fees
            if "credit note" in combined_text.casefold() or "credit memo" in combined_text.casefold():
                amount_paid = 0.0 if amount_paid is None else amount_paid
                if payment_terms and payment_terms.endswith("...") and refund_method:
                    payment_terms = f"Refund to {refund_method.casefold()}"
            else:
                refund = 0.0 if refund is None else refund
            if items and tax is not None and subtotal is not None and all(item.get("tax_rate") is None for item in items):
                taxable_base = abs(subtotal) - abs(discount or 0.0)
                if taxable_base > 0:
                    inferred_rate = round(abs(tax) / taxable_base, 4)
                    for item in items:
                        item["tax_rate"] = inferred_rate
                        item["tax_amount"] = round(item["amount"] * inferred_rate, 2)
                        item["line_total"] = round(item["amount"] + item["tax_amount"], 2)

        if subtotal is None and items:
            subtotal = round(sum(item["amount"] for item in items), 2)
        if document_type == "receipt":
            tax = 0.0 if tax is None else tax
            tip = 0.0 if tip is None else tip
        warnings: list[dict[str, str]] = []
        if not all_lines:
            warnings.append({"code": "no_text", "message": "No readable text was found in the PDF."})
        if ocr_missing and not ocr_available():
            warnings.append(
                {"code": "ocr_unavailable", "message": "A scanned page was detected, but the local OCR runtime is not installed."}
            )
        if merchant is None:
            warnings.append({"code": "merchant_missing", "message": "Merchant could not be identified."})
        if total is None:
            warnings.append({"code": "total_missing", "message": "Total amount could not be identified."})
        if not items and document_type in {"receipt", "invoice"}:
            warnings.append({"code": "items_missing", "message": "No line items were identified."})

        difference = None
        matched = None
        if total is not None and subtotal is not None:
            difference = round(total - subtotal - (tax or 0.0) - (tip or 0.0), 2)
            matched = abs(difference) <= 0.02
            if not matched:
                warnings.append({"code": "totals_mismatch", "message": "Subtotal plus tax and tip does not match the total."})

        fields = {
            "merchant": _field(merchant, merchant_line, 0.92),
            "vendor_address": _field(vendor_address, vendor_address_line, 0.94),
            "vendor_tax_id": _field(vendor_tax_id, vendor_tax_id_line, 0.94),
            "customer_name": _field(bill_to_name, bill_to_name_line, 0.94),
            "customer_address": _field(bill_to_address, bill_to_address_line, 0.94),
            "bill_to_name": _field(bill_to_name, bill_to_name_line, 0.94),
            "bill_to_address": _field(bill_to_address, bill_to_address_line, 0.94),
            "ship_to_name": _field(ship_to_name, ship_to_name_line, 0.94),
            "ship_to_address": _field(ship_to_address, ship_to_address_line, 0.94),
            "date": _field(date, date_line, 0.96),
            "due_date": _field(due_date, due_date_line, 0.94),
            "currency": _field(currency, currency_line, 0.95 if currency_line else 0.6),
            "receipt_number": _field(receipt_number, number_line, 0.94),
            "original_invoice_number": _field(original_invoice, original_invoice_line, 0.94),
            "account_number": _field(account_number, account_line, 0.9),
            "purchase_order_number": _field(purchase_order, purchase_order_line, 0.9),
            "payment_terms": _field(payment_terms, payment_terms_line, 0.9),
            "discount": _field(discount, discount_line, 0.9),
            "refund": _field(refund, refund_line, 0.9),
            "subtotal": _field(subtotal, subtotal_line, 0.93 if subtotal_line else 0.72),
            "shipping": _field(shipping, shipping_line, 0.9),
            "fees": _field(fees, fees_line, 0.88),
            "tax": _field(tax, tax_line, 0.91 if tax_line else 0.65),
            "tip": _field(tip, tip_line, 0.91 if tip_line else 0.65),
            "total": _field(total, total_line, 0.96),
            "amount_paid": _field(amount_paid, amount_paid_line, 0.9),
            "balance_due": _field(balance_due, balance_due_line, 0.95),
            "previous_balance": _field(previous_balance, previous_balance_line, 0.9),
            "payments": _field(payments, payments_line, 0.9),
            "credits": _field(credits, credits_line, 0.9),
            "adjustments": _field(adjustments, adjustments_line, 0.88),
            "current_charges": _field(current_charges, current_charges_line, 0.92),
            "late_fee": _field(late_fee, late_fee_line, 0.9),
            "minimum_due": _field(minimum_due, minimum_due_line, 0.9),
            "payment_method": _field(payment, payment_line, 0.9),
        }
        confidence_values = [field["confidence"] for field in fields.values() if field["value"] is not None]
        confidence_values.extend(item["confidence"] for item in items)
        overall_confidence = round(mean(confidence_values), 3) if confidence_values else 0.0
        extraction_method = (
            "mixed" if len(set(methods) - {"none"}) > 1 else next((method for method in methods if method != "none"), "none")
        )
        status = "needs_review" if warnings or overall_confidence < 0.85 else "ready"

        result = {
            "schema_version": "1.0",
            "document_type": document_type,
            "status": status,
            "page_count": document.page_count,
            "extraction_method": extraction_method,
            "overall_confidence": overall_confidence,
            "fields": fields,
            "items": items,
            "reconciliation": {"matched": matched, "difference": difference},
            "warnings": warnings,
            "pages": page_texts,
        }
        finalize_document_result(result, text=combined_text, document_type=document_type)
        return result, preview
    finally:
        document.close()
