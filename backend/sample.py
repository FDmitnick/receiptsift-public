from __future__ import annotations


def create_sample_pdf() -> bytes:
    """Build a deterministic one-page receipt for demos and integration tests."""
    import pymupdf

    lines = [
        "CEDAR & FINCH KITCHEN",
        "418 West 2nd Street, Austin, TX",
        "Receipt No: CF-1842",
        "Date: 2026-08-18 19:42",
        "Grilled Chicken Bowl 1 x 16.00 16.00",
        "House Lemonade       2 x 4.50   9.00",
        "Subtotal                       25.00",
        "Tax                             2.06",
        "Total USD                      27.06",
        "Payment: VISA",
        "Thank you",
    ]
    document = pymupdf.open()
    page = document.new_page(width=320, height=520)
    y = 54
    for index, line in enumerate(lines):
        size = 13 if index == 0 else 10
        page.insert_text((30, y), line, fontsize=size, fontname="cour")
        y += 34 if index == 0 else 28
    payload = document.tobytes(deflate=True)
    document.close()
    return payload
