"""Direct Coil 'COIL QUOTE' cover detector: one cover row per numbered coil item.

Additive to the existing cover detection — the Oxygen8 submittal path is untouched.
Covers both text layouts the PDF engines produce: pdfplumber renders ``Tagged: CODE``
inline, fitz splits the label and value across two lines.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal.pdf_intake import (  # noqa: E402
    _TextPage,
    _detect_cover_page_from_direct_coil_quote,
)

# pdfplumber layout: "label: value" inline on one line.
_QUOTE_INLINE = """COIL QUOTE
Company: Date: 6/23/2026
1. 3DX-05-15.0-10-47.0-9 Direct Expansion Coil
Handing: Left
Quantity: 1
Tagged: CDXC-1
Cost Each: CAD$1,952.00 Item 1 Total: CAD$1,952.00
2. 3DC-02-15.0-08-47.0-3 Condenser Coil
Handing: Left
Quantity: 1
Tagged: RHHGRC-1
Cost Each: CAD$960.00 Item 2 Total: CAD$960.00
Total Cost (All Items): CAD$2,912.00
"""

# fitz layout: label on its own line, value on the next line.
_QUOTE_SPLIT = """COIL QUOTE
1.
3DX-05-15.0-10-47.0-9 Direct Expansion Coil
Handing:
Left
Quantity:
1
Tagged:
CDXC-1
2.
3DC-02-15.0-08-47.0-3 Condenser Coil
Handing:
Left
Quantity:
1
Tagged:
RHHGRC-1
"""


def test_detects_both_coils_inline_layout() -> None:
    det = _detect_cover_page_from_direct_coil_quote(_TextPage(page_number=1, text=_QUOTE_INLINE))
    assert det.detected
    assert det.detection_method == "direct_coil_quote_numbered_items"
    assert [row.tag for row in det.rows] == ["CDXC-1", "RHHGRC-1"]
    assert [row.row_number for row in det.rows] == [1, 2]
    assert all(row.qty == 1 for row in det.rows)


def test_detects_both_coils_split_layout() -> None:
    det = _detect_cover_page_from_direct_coil_quote(_TextPage(page_number=1, text=_QUOTE_SPLIT))
    assert det.detected
    assert [row.tag for row in det.rows] == ["CDXC-1", "RHHGRC-1"]


def test_non_quote_page_not_detected() -> None:
    det = _detect_cover_page_from_direct_coil_quote(
        _TextPage(page_number=1, text="DX COIL REPORT\nSome other content\nCDXC-1")
    )
    assert det.detected is False


def test_quote_without_coil_tags_not_detected() -> None:
    det = _detect_cover_page_from_direct_coil_quote(
        _TextPage(page_number=1, text="COIL QUOTE\n1. Some accessory\nTagged: EKEXV-1")
    )
    # EKEXV is a non-coil tag prefix -> no coil rows -> not a usable cover page.
    assert det.detected is False
