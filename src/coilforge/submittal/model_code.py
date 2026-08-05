"""Read the drain-pan option out of an Oxygen8 unit model code. Pure, no I/O.

The full unit model code is a 22-token underscore run that the submittal prints on its
configuration pages::

    TR_C_012_I_R_1_H11_21_XSXS_V_XX_X_X_X_XX_XX_X_XXX_XX_X_X_X
     0  1  2  3 4 5  6  7                    ^ index 7 = the control/drain-pan token

Token 7 is always two digits: the FIRST is the control quantity, the SECOND is the
drain-pan type (1/2/3 -> D1/D2/D3). John confirmed the position for **Terra H**.

Everything this module refuses to answer, it refuses loudly
-----------------------------------------------------------
Every rejection returns ``(None, reason)`` with a specific reason string, never a bare
``None`` and never a guess. R-077 keys Terra's drain-pan width by that D-option, so a
wrong option silently produces a plausible width for the wrong pan — the failure mode
that has no visible symptom.

**Terra V is deliberately not parsed here.** Its widths are keyed by unit SIZE, not by a
D-option (R-077 has no ``TERRA|D*`` arm that applies to it and its size rows are still
TBD), so returning "D1" for a Terra V unit would hand a Terra H width to a vertical unit.
Its codes do carry a two-digit token at index 7 — that is exactly why the guard has to be
explicit rather than relying on the parse failing.

**On "Terra H C":** the schedule code has no separate form for it. ``TR_[CV]_###`` carries
only the H/V orientation (``coilmaster_drawing_extract._TERRA_MODEL_RE``), and the
``TERRA_H_C`` variant that ``resolve_product_line`` attaches to every ``TERRA H`` label is
not distinguishable from the code. So a per-code Terra-H-C exclusion is not expressible;
what IS confirmed is that a ``TR_C_###`` schedule code is the Terra H form John checked,
and that is what this module parses.
"""
from __future__ import annotations

import re

#: Index of the control/drain-pan token in the underscore-split model code.
_DRAIN_PAN_TOKEN_INDEX = 7

#: Minimum token count for index 7 to exist at all.
_MIN_TOKENS = _DRAIN_PAN_TOKEN_INDEX + 1

#: Second digit -> drain-pan option.
_OPTION_BY_DIGIT = {"1": "D1", "2": "D2", "3": "D3"}

# A full underscore-joined model code starting with a Terra schedule prefix. Anchored on
# the prefix rather than searched loosely so a stray underscore run elsewhere on the page
# cannot be read as a model code.
_TERRA_H_RUN = re.compile(r"\bTR_C_\d{1,3}(?:_[A-Za-z0-9]+)+", re.IGNORECASE)
_TERRA_V_RUN = re.compile(r"\b(?:TR_V|TV_[A-Z])_\d{1,3}(?:_[A-Za-z0-9]+)+", re.IGNORECASE)


def find_model_code_run(text: str | None) -> str | None:
    """The longest full (underscore-joined) unit model code in ``text``, or ``None``.

    Returned for STORAGE IN A DEDICATED FIELD ONLY. It must never be written into
    ``row.model`` / ``candidate.notes``: ``detect_product_and_size`` mis-reads a full code
    (the trailing ``\\b`` in its Terra regexes cannot match a code that continues with
    ``_``), so a Terra V code resolves to ``('VENTUM_H','H10')`` off its inner size token
    and a Terra H code resolves to ``(None, None)``. Both are silent — see
    ``tests/test_model_code.py``.
    """
    if not text:
        return None
    hits = _TERRA_H_RUN.findall(text) + _TERRA_V_RUN.findall(text)
    if not hits:
        return None
    return max(hits, key=lambda s: len(s.split("_")))


def find_model_code_runs(text: str | None) -> list[str]:
    """Every distinct full model code in ``text``, longest-first."""
    if not text:
        return []
    hits = _TERRA_H_RUN.findall(text) + _TERRA_V_RUN.findall(text)
    seen: dict[str, None] = {}
    for hit in hits:
        seen.setdefault(hit.upper(), None)
    return sorted(seen, key=lambda s: -len(s.split("_")))


def unit_size_from_model_code(code: str | None) -> str | None:
    """The zero-padded unit size the code carries at token 2 (``TR_C_012`` -> ``"012"``)."""
    if not code:
        return None
    tokens = str(code).upper().split("_")
    if len(tokens) < 3 or not tokens[2].isdigit():
        return None
    return f"{int(tokens[2]):03d}"


def drain_pan_options_by_unit_size(text: str | None) -> dict[str, tuple[str | None, str]]:
    """``{unit_size: (option, reason)}`` for every full model code in a submittal.

    Attribution, not parsing, is the hard part. The full model code does not sit on the
    cover schedule next to a coil tag — it is alone on a configuration page (2948 p8,
    2755 p62/p73), so there is no row to join it to and a document-wide scan is the only
    way to see it. The code's OWN unit size (token 2) is what supplies the join.

    Keying by unit size, rather than applying one code to the whole document, is a
    correction the real data forced: 2755 is a MULTI-unit submittal (sizes 009 and 012)
    that prints only ONE full code. A "single distinct code means single unit" rule reads
    as true there and silently hands the 012 unit's pan option to the 009 unit. Different
    units can carry different pans, so that is a wrong width with no visible symptom.

    A size with no code is simply absent — the caller reports it as unresolved rather than
    borrowing another unit's option. Two codes for the SAME size that disagree collapse to
    a refusal for that size, since nothing distinguishes them.
    """
    index: dict[str, tuple[str | None, str]] = {}
    for code in find_model_code_runs(text):
        size = unit_size_from_model_code(code)
        if size is None:
            continue
        option, reason = drain_pan_option_from_model_code(code)
        prior = index.get(size)
        if prior is not None and prior[0] != option:
            index[size] = (
                None,
                f"two model codes for unit size {size} disagree on the drain-pan option "
                f"({prior[0]} vs {option}) — set it per coil instead of guessing",
            )
            continue
        index[size] = (option, reason)
    return index


def drain_pan_option_for_unit_size(
    text: str | None, unit_size: str | None
) -> tuple[str | None, str]:
    """Drain-pan option for ONE unit size within a submittal, or ``(None, reason)``."""
    if not unit_size:
        return None, "the coil's unit size is unresolved, so its model code cannot be found"
    index = drain_pan_options_by_unit_size(text)
    if not index:
        return None, "no full unit model code found in the submittal text"
    try:
        key = f"{int(str(unit_size)):03d}"
    except (TypeError, ValueError):
        key = str(unit_size).upper()
    if key not in index:
        return None, (
            f"no unit model code for size {unit_size} appears in this submittal "
            f"(found: {', '.join(sorted(index))}) — it deliberately does not borrow "
            "another unit's drain-pan option"
        )
    return index[key]


def drain_pan_option_from_model_code(text: str | None) -> tuple[str | None, str]:
    """``("D1"|"D2"|"D3", reason)`` or ``(None, reason)``. Never raises, never guesses.

    The reason is populated on success too, so a caller can show WHY a coil is evaluating
    against a particular pan without re-deriving it.
    """
    if not text or not str(text).strip():
        return None, "no model code text to read"

    code = find_model_code_run(str(text))
    if code is None:
        return None, "no full underscore-joined Terra model code found in the text"

    upper = code.upper()
    if not upper.startswith("TR_C_"):
        # Terra V (TR_V_### / TV_?_###) or anything else that matched the V pattern.
        return None, (
            "Terra V drain-pan width is keyed by unit size, not by a D1/D2/D3 option, so "
            "the token at this position does not describe its pan — refusing to read it"
        )

    tokens = upper.split("_")
    if len(tokens) < _MIN_TOKENS:
        return None, (
            f"model code has {len(tokens)} tokens; the drain-pan token is at index "
            f"{_DRAIN_PAN_TOKEN_INDEX} and is not present"
        )

    token = tokens[_DRAIN_PAN_TOKEN_INDEX]
    if not (len(token) == 2 and token.isdigit()):
        return None, (
            f"the token at index {_DRAIN_PAN_TOKEN_INDEX} is {token!r}; the drain-pan "
            "token is always exactly two digits (control qty, then pan type)"
        )

    option = _OPTION_BY_DIGIT.get(token[1])
    if option is None:
        return None, (
            f"drain-pan digit {token[1]!r} in token {token!r} is not one of 1/2/3 — "
            "no D-option corresponds to it"
        )
    return option, (
        f"read from model-code token {token!r} (index {_DRAIN_PAN_TOKEN_INDEX}); "
        f"second digit {token[1]} -> {option}"
    )
