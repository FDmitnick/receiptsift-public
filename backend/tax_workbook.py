from __future__ import annotations

import io
import math
import re
import zipfile
from datetime import UTC, date, datetime
from typing import Any
from xml.sax.saxutils import escape, quoteattr

SCHEDULE_C_CATEGORIES = (
    "Line 8 - Advertising",
    "Line 9 - Car and truck expenses",
    "Line 10 - Commissions and fees",
    "Line 11 - Contract labor",
    "Line 12 - Depletion",
    "Line 13 - Depreciation and section 179",
    "Line 14 - Employee benefit programs",
    "Line 15 - Insurance (other than health)",
    "Line 16a - Mortgage interest",
    "Line 16b - Other interest",
    "Line 17 - Legal and professional services",
    "Line 18 - Office expense",
    "Line 19 - Pension and profit-sharing plans",
    "Line 20a - Rent or lease: vehicles, machinery, equipment",
    "Line 20b - Rent or lease: other business property",
    "Line 21 - Repairs and maintenance",
    "Line 22 - Supplies",
    "Line 23 - Taxes and licenses",
    "Line 24a - Travel",
    "Line 24b - Deductible meals",
    "Line 25 - Utilities",
    "Line 26 - Wages",
    "Line 27a - Other expenses",
    "Part III - Cost of goods sold or inventory",
    "Review separately - asset or capital expenditure",
    "Personal or nonbusiness",
)


def _result(document: dict[str, Any]) -> dict[str, Any]:
    result = document.get("result")
    return result if isinstance(result, dict) else {}


def _field(result: dict[str, Any], name: str) -> Any:
    value = (result.get("fields") or {}).get(name)
    return value.get("value") if isinstance(value, dict) else None


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _excel_date(value: Any) -> float | None:
    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    return float((parsed - date(1899, 12, 30)).days)


def _cell(reference: str, value: Any = None, *, style: int = 0, formula: str | None = None) -> str:
    style_attr = f' s="{style}"' if style else ""
    if formula is not None:
        return f'<c r="{reference}"{style_attr}><f>{escape(formula)}</f></c>'
    if value is None or value == "":
        return f'<c r="{reference}"{style_attr}/>'
    if isinstance(value, bool):
        return f'<c r="{reference}"{style_attr} t="b"><v>{1 if value else 0}</v></c>'
    number = _finite_number(value)
    if number is not None and not isinstance(value, str):
        return f'<c r="{reference}"{style_attr} t="n"><v>{number}</v></c>'
    text = str(value)
    preserve = ' xml:space="preserve"' if text != text.strip() or "\n" in text else ""
    return f'<c r="{reference}"{style_attr} t="inlineStr"><is><t{preserve}>{escape(text)}</t></is></c>'


def _sheet_xml(
    rows: list[list[tuple[Any, int, str | None]]],
    *,
    widths: list[float],
    freeze_row: int | None = None,
    auto_filter: str | None = None,
    data_validations: list[str] | None = None,
    merges: list[str] | None = None,
    hidden: bool = False,
) -> str:
    max_columns = max((len(row) for row in rows), default=1)
    max_rows = max(len(rows), 1)
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, (value, style, formula) in enumerate(row, start=1):
            cells.append(_cell(f"{_column_name(column_index)}{row_index}", value, style=style, formula=formula))
        height = ' ht="30" customHeight="1"' if row_index == 1 else ""
        row_xml.append(f'<row r="{row_index}"{height}>{"".join(cells)}</row>')
    columns = "".join(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>' for index, width in enumerate(widths, start=1))
    pane = ""
    if freeze_row:
        pane = (
            '<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
            f'<pane ySplit="{freeze_row}" topLeftCell="A{freeze_row + 1}" activePane="bottomLeft" state="frozen"/>'
            "</sheetView></sheetViews>"
        )
    else:
        pane = '<sheetViews><sheetView workbookViewId="0" showGridLines="0"/></sheetViews>'
    filter_xml = f'<autoFilter ref="{auto_filter}"/>' if auto_filter else ""
    validations_xml = ""
    if data_validations:
        validations_xml = f'<dataValidations count="{len(data_validations)}">{"".join(data_validations)}</dataValidations>'
    merges_xml = ""
    if merges:
        merge_cells = "".join(f'<mergeCell ref="{cell_range}"/>' for cell_range in merges)
        merges_xml = f'<mergeCells count="{len(merges)}">{merge_cells}</mergeCells>'
    visibility = '<sheetPr><outlinePr summaryBelow="1" summaryRight="1"/></sheetPr>' if hidden else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'{visibility}<dimension ref="A1:{_column_name(max_columns)}{max_rows}"/>{pane}'
        f'<sheetFormatPr defaultRowHeight="15"/><cols>{columns}</cols><sheetData>{"".join(row_xml)}</sheetData>{merges_xml}'
        f'{filter_xml}{validations_xml}<pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
        "</worksheet>"
    )


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="4">
    <numFmt numFmtId="164" formatCode="yyyy-mm-dd"/>
    <numFmt numFmtId="165" formatCode="$#,##0.00;[Red]($#,##0.00);-"/>
    <numFmt numFmtId="166" formatCode="0.0%"/>
    <numFmt numFmtId="167" formatCode="#,##0.00;[Red](#,##0.00);-"/>
  </numFmts>
  <fonts count="6">
    <font><sz val="10"/><name val="Aptos"/><family val="2"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="18"/><name val="Aptos Display"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="10"/><name val="Aptos"/></font>
    <font><color rgb="FF0000FF"/><sz val="10"/><name val="Aptos"/></font>
    <font><color rgb="FF008000"/><sz val="10"/><name val="Aptos"/></font>
    <font><b/><color rgb="FF9C0006"/><sz val="10"/><name val="Aptos"/></font>
  </fonts>
  <fills count="6">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF162238"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF0F766E"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFE4E1"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border><left/><right/><top/><bottom style="thin"><color rgb="FFD9E0E7"/></bottom><diagonal/></border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="12">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center"/></xf>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1">
      <alignment vertical="center" wrapText="1"/>
    </xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="165" fontId="4" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1"/>
    <xf numFmtId="164" fontId="4" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment wrapText="1"/></xf>
    <xf numFmtId="166" fontId="3" fillId="4" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyBorder="1"/>
    <xf numFmtId="165" fontId="5" fillId="5" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="167" fontId="4" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyFont="1" applyBorder="1"/>
    <xf numFmtId="0" fontId="5" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
  <dxfs count="0"/><tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>"""


def _warning_text(document: dict[str, Any], result: dict[str, Any]) -> str:
    messages = [
        str(warning.get("message") or warning.get("code") or "") for warning in result.get("warnings", []) if isinstance(warning, dict)
    ]
    if document.get("error_code"):
        messages.append(str(document["error_code"]))
    missing = [name for name in ("vendor_name", "issue_date", "currency", "total") if _field(result, name) in (None, "")]
    if missing:
        messages.append(f"Missing: {', '.join(missing)}")
    return "; ".join(filter(None, messages))


def schedule_c_workbook(documents: list[dict[str, Any]], *, batch_name: str = "ReceiptSift batch") -> bytes:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    last_row = max(6, 5 + len(documents))

    instructions = [
        [("ReceiptSift tax-preparation workbook", 1, None)],
        [
            ("Purpose", 2, None),
            (
                "Organize reviewed financial documents for a U.S. sole proprietor or independent contractor "
                "and hand them to a tax professional or approved tax software.",
                3,
                None,
            ),
        ],
        [
            ("Important", 2, None),
            (
                "This workbook is not a tax return and cannot be filed directly with the IRS. "
                "ReceiptSift does not decide whether an expense is deductible.",
                11,
                None,
            ),
        ],
        [
            ("How to use", 2, None),
            (
                "Review every source PDF. In Transactions, choose a candidate Schedule C category and enter "
                "the tax-basis amount, business-use percentage, and allowed percentage. "
                "The Summary sheet then calculates from those inputs.",
                3,
                None,
            ),
        ],
        [
            ("Tax shown", 2, None),
            (
                "Sales tax printed on a document is shown separately for bookkeeping. "
                "It is not automatically treated as a separate deduction.",
                3,
                None,
            ),
        ],
        [
            ("Records", 2, None),
            (
                "Keep the original receipts, invoices, bills, and proof of payment. "
                "This workbook is only an index and summary of supporting records.",
                3,
                None,
            ),
        ],
        [("Batch", 2, None), (batch_name, 3, None)],
        [("Generated at", 2, None), (generated_at, 3, None)],
        [
            ("IRS recordkeeping", 2, None),
            ("https://www.irs.gov/businesses/small-businesses-self-employed/what-kind-of-records-should-i-keep", 3, None),
        ],
        [("Schedule C instructions", 2, None), ("https://www.irs.gov/instructions/i1040sc", 3, None)],
        [("IRS e-file format", 2, None), ("https://www.irs.gov/e-file-providers/modernized-e-file-overview", 3, None)],
    ]

    transaction_headers = (
        "Document ID",
        "Source file",
        "Source SHA-256",
        "Review status",
        "Issue date",
        "Vendor / payee",
        "Document type",
        "Document number",
        "Currency",
        "Subtotal",
        "Tax shown",
        "Document total",
        "Amount paid",
        "Balance due",
        "Candidate Schedule C category",
        "Tax-basis amount",
        "Business use %",
        "Allowed %",
        "Prepared amount",
        "Review notes",
        "Source PDF retained",
    )
    transactions: list[list[tuple[Any, int, str | None]]] = [
        [("Transactions requiring user or accountant classification", 1, None)],
        [
            (
                "Blue/yellow cells are user inputs. Green values came from parsed documents. "
                "Prepared amount stays blank until all four inputs are supplied.",
                3,
                None,
            )
        ],
        [],
        [],
        [(header, 2, None) for header in transaction_headers],
    ]
    for offset, document in enumerate(documents, start=6):
        result = _result(document)
        issue_date = _excel_date(_field(result, "issue_date"))
        formula = f'IF(OR(O{offset}="",P{offset}="",Q{offset}="",R{offset}=""),"",P{offset}*Q{offset}*R{offset})'
        transactions.append(
            [
                (document.get("id"), 3, None),
                (document.get("filename"), 3, None),
                (document.get("sha256"), 3, None),
                (document.get("status") or result.get("status"), 11 if document.get("status") != "ready" else 3, None),
                (issue_date if issue_date is not None else _field(result, "issue_date"), 5 if issue_date is not None else 3, None),
                (_field(result, "vendor_name"), 3, None),
                (result.get("document_type"), 3, None),
                (_field(result, "document_number"), 3, None),
                (_field(result, "currency"), 3, None),
                (_finite_number(_field(result, "subtotal")), 4, None),
                (_finite_number(_field(result, "tax")), 4, None),
                (_finite_number(_field(result, "total")), 4, None),
                (_finite_number(_field(result, "amount_paid")), 4, None),
                (_finite_number(_field(result, "balance_due")), 4, None),
                (None, 6, None),
                (None, 6, None),
                (None, 7, None),
                (None, 7, None),
                (None, 8, formula),
                (_warning_text(document, result), 11 if _warning_text(document, result) else 3, None),
                ("Yes" if document.get("source_available") else "No", 3, None),
            ]
        )

    validation_category = (
        f'<dataValidation type="list" allowBlank="1" showErrorMessage="1" sqref="O6:O{last_row}">'
        "<formula1>ScheduleCCategories</formula1></dataValidation>"
    )
    validation_amount = (
        f'<dataValidation type="decimal" operator="greaterThanOrEqual" allowBlank="1" sqref="P6:P{last_row}">'
        "<formula1>0</formula1></dataValidation>"
    )
    validation_business = (
        f'<dataValidation type="decimal" operator="between" allowBlank="1" sqref="Q6:R{last_row}">'
        "<formula1>0</formula1><formula2>1</formula2></dataValidation>"
    )

    summary = [
        [("Schedule C-style preparation summary", 1, None)],
        [
            (
                "These are preparation categories, not filing determinations. "
                "Confirm the applicable form and tax year with a qualified professional.",
                3,
                None,
            )
        ],
        [],
        [("Candidate category", 2, None), ("Prepared amount", 2, None), ("Documents", 2, None)],
    ]
    for row_index, category in enumerate(SCHEDULE_C_CATEGORIES, start=5):
        summary.append(
            [
                (category, 3, None),
                (None, 8, f"SUMIF('Transactions'!$O$6:$O${last_row},A{row_index},'Transactions'!$S$6:$S${last_row})"),
                (None, 10, f"COUNTIF('Transactions'!$O$6:$O${last_row},A{row_index})"),
            ]
        )
    total_row = 5 + len(SCHEDULE_C_CATEGORIES)
    summary.append([("Total prepared amount", 2, None), (None, 8, f"SUM(B5:B{total_row - 1})"), (None, 10, f"SUM(C5:C{total_row - 1})")])
    summary.append(
        [
            ("Unclassified documents", 11, None),
            (None, 10, f"COUNTIFS('Transactions'!$A$6:$A${last_row},\"<>\",'Transactions'!$O$6:$O${last_row},\"\")"),
        ]
    )

    exceptions = [[("Exceptions and unresolved documents", 1, None)], [("Source file", 2, None), ("Status", 2, None), ("Issues", 2, None)]]
    for document in documents:
        result = _result(document)
        issue = _warning_text(document, result)
        if document.get("status") != "ready" or issue:
            exceptions.append(
                [(document.get("filename"), 3, None), (document.get("status"), 11, None), (issue or "Review required", 11, None)]
            )
    if len(exceptions) == 2:
        exceptions.append([("No unresolved documents in this export.", 3, None)])

    line_items = [
        [("Extracted line items", 1, None)],
        [
            ("Source file", 2, None),
            ("Document number", 2, None),
            ("Description", 2, None),
            ("SKU", 2, None),
            ("Quantity", 2, None),
            ("Unit", 2, None),
            ("Unit price", 2, None),
            ("Line discount", 2, None),
            ("Tax rate", 2, None),
            ("Tax amount", 2, None),
            ("Line amount", 2, None),
        ],
    ]
    for document in documents:
        result = _result(document)
        for item in result.get("items", []) if isinstance(result.get("items"), list) else []:
            line_items.append(
                [
                    (document.get("filename"), 3, None),
                    (_field(result, "document_number"), 3, None),
                    (item.get("description"), 3, None),
                    (item.get("sku"), 3, None),
                    (_finite_number(item.get("quantity")), 10, None),
                    (item.get("unit"), 3, None),
                    (_finite_number(item.get("unit_price")), 4, None),
                    (_finite_number(item.get("discount")), 4, None),
                    (_finite_number(item.get("tax_rate")), 10, None),
                    (_finite_number(item.get("tax_amount")), 4, None),
                    (_finite_number(item.get("amount")), 4, None),
                ]
            )
    if len(line_items) == 2:
        line_items.append([("No line items were extracted.", 3, None)])

    categories = [[("Category list", 2, None)]] + [[(category, 3, None)] for category in SCHEDULE_C_CATEGORIES]
    sheets = [
        ("Instructions", _sheet_xml(instructions, widths=[24, 105], merges=["A1:B1"])),
        (
            "Transactions",
            _sheet_xml(
                transactions,
                widths=[17, 27, 34, 15, 13, 25, 14, 18, 10, 14, 14, 14, 14, 14, 48, 16, 14, 14, 16, 48, 18],
                freeze_row=5,
                auto_filter=f"A5:U{last_row}",
                data_validations=[validation_category, validation_amount, validation_business],
                merges=["A1:U1", "A2:U2"],
            ),
        ),
        (
            "Schedule C Summary",
            _sheet_xml(summary, widths=[62, 20, 14], freeze_row=4, merges=["A1:C1", "A2:C2"]),
        ),
        (
            "Exceptions",
            _sheet_xml(
                exceptions,
                widths=[32, 16, 100],
                freeze_row=2,
                auto_filter=f"A2:C{max(2, len(exceptions))}",
                merges=["A1:C1"],
            ),
        ),
        (
            "Line Items",
            _sheet_xml(
                line_items,
                widths=[28, 20, 42, 18, 12, 12, 16, 16, 13, 16, 16],
                freeze_row=2,
                auto_filter=f"A2:K{max(2, len(line_items))}",
                merges=["A1:K1"],
            ),
        ),
        ("Categories", _sheet_xml(categories, widths=[64])),
    ]

    workbook_sheets = "".join(
        f'<sheet name={quoteattr(name)} sheetId="{index}" state="{("hidden" if name == "Categories" else "visible")}" r:id="rId{index}"/>'
        for index, (name, _) in enumerate(sheets, start=1)
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<bookViews><workbookView activeTab="1"/></bookViews><sheets>{workbook_sheets}</sheets>'
        "<definedNames><definedName name=\"ScheduleCCategories\">'Categories'!$A$2:$A$27</definedName></definedNames>"
        '<calcPr calcId="191029" fullCalcOnLoad="1" forceFullCalc="1"/></workbook>'
    )
    relationships = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    relationships += (
        f'<Relationship Id="rId{len(sheets) + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{relationships}</Relationships>"
    )
    content_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{content_overrides}"
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="xl/workbook.xml"/>
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties"
    Target="docProps/core.xml"/>
  <Relationship Id="rId3"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties"
    Target="docProps/app.xml"/>
</Relationships>"""
    core = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
  xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>ReceiptSift tax-preparation workbook</dc:title>
  <dc:creator>ReceiptSift</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">{generated_at}</dcterms:created>
</cp:coreProperties>"""
    app = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>ReceiptSift</Application></Properties>"""

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("docProps/core.xml", core)
        archive.writestr("docProps/app.xml", app)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, (_, xml) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", xml)
    return output.getvalue()
