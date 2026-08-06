"""Read values a human entered into the CCSI 'Direct Coil' web form.

This is the *read* half of the Phase 2 "read-and-alert" verifier (workflow step 6).
CoilForge never edits the Direct Coil website; John fills it in himself, and this
module turns the captured page text — whether browser-read (Claude-in-Chrome
``get_page_text``) or pasted into the UI — into a plain ``{normalized_key: value}``
dict that the comparator (``verify.py``) can diff against CoilForge's canonical record.

It is a pure, deterministic parser with no I/O. It never invents a value: a label
that is absent (or has a blank value) simply does not appear in the result. The
field labels and ``normalized_key``s are reused verbatim from the paste-ready
surface (``DIRECT_COIL_PASTE_FIELD_ORDER``) so the read side and the existing
paste side stay in lockstep.

Two page layouts are handled, the same lesson learned in the Phase 1+ quote cover
detector: ``Label: value`` inline on one line (text copy / pdfplumber) and
``Label:`` followed by ``value`` on the next line (DOM text dumps).
"""

from __future__ import annotations

import re
from typing import Any

from coilforge.direct_coil.paste_ready_fields import DIRECT_COIL_PASTE_FIELD_ORDER


def _normalize_label(label: str) -> str:
    """Case-folded, whitespace-collapsed form so DOM/text label variants still match."""
    return re.sub(r"\s+", " ", label).strip().casefold()


def _base_label(label: str) -> str:
    """Label with any trailing parenthetical unit dropped ('Finned Height(In)' ->
    'Finned Height'). A fallback for pages that render the bare label without units."""
    return _normalize_label(label.split("(", 1)[0])


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _value_after_label(lines: list[str], wanted: tuple[str, str]) -> str:
    """First value for ``label`` within ``lines``.

    ``wanted`` is ``(full_label_norm, base_label_norm)``. Inline ``Label: value``
    wins; otherwise a bare ``Label`` / ``Label:`` line takes the next non-empty
    line as its value. Matching is anchored so a single-letter dimension label
    ('I', 'S') cannot false-match an arbitrary word ('Item:')."""
    full, base = wanted
    for index, raw in enumerate(lines):
        cleaned = _clean(raw)
        if not cleaned:
            continue
        head, sep, tail = cleaned.partition(":")
        head_norm = _normalize_label(head)
        if sep and head_norm in (full, base):
            value = tail.strip()
            if value:
                return value
            # bare "Label:" with the value on a following line
            for nxt in lines[index + 1 :]:
                nxt_clean = _clean(nxt)
                if nxt_clean:
                    return nxt_clean
            return ""
        if not sep and head_norm in (full, base):
            for nxt in lines[index + 1 :]:
                nxt_clean = _clean(nxt)
                if nxt_clean:
                    return nxt_clean
            return ""
    return ""


def parse_direct_coil_page(text: str) -> dict[str, Any]:
    """Parse Direct Coil page text into ``{normalized_key: raw_value}``.

    Keyed by the paste-surface ``normalized_key`` so the comparator can align each
    entered value with its canonical field. Absent/blank labels are omitted."""
    lines = (text or "").splitlines()
    result: dict[str, Any] = {}
    for spec in DIRECT_COIL_PASTE_FIELD_ORDER:
        wanted = (_normalize_label(spec.label), _base_label(spec.label))
        value = _value_after_label(lines, wanted)
        if value:
            result[spec.normalized_key] = value
    return result


def direct_coil_page_coverage(text: str) -> dict[str, Any]:
    """How much of the page was actually read — the anti-false-reassurance signal.

    ``comparable_label_count`` is how many Direct Coil fields the parser looks for;
    ``fields_read`` is how many it found a value for. A near-empty parse must NOT be
    allowed to masquerade as a clean verification, so the comparator surfaces these."""
    found = parse_direct_coil_page(text)
    return {
        "found_keys": sorted(found),
        "fields_read": len(found),
        "comparable_label_count": len(DIRECT_COIL_PASTE_FIELD_ORDER),
    }
