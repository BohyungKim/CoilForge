"""Structural reference for "Coil Checklist Template.xlsx" (pure data, no I/O).

Transcribed by Phase-0 introspection of the live workbook on 2026-06-30 via Excel
COM (sheets: HWC, CWC, DX, HGRH, "Install | Drain Pan Width", Units). Nothing here
opens Excel — the writer/mapping import these constants so they can be unit-tested
without the workbook present.

Key facts that shape the writer:
- Checkboxes are **native Excel boolean cell-checkboxes** (not form/ActiveX
  controls): set one by writing ``True``/``False`` to its column-C cell; never
  clear the cell's checkbox format.
- Field name lives in column **B**; the value the engineer fills lives in column
  **C** ("SUBMITTAL"). Column D ("SELECTION") and column E ("WARNING") are left
  untouched. The writer locates a field by scanning column B for its label, so it
  is robust to row shifts and to the per-sheet layout differences captured below.
- The four CATEGORY sheets (DX/HGRH/HWC/CWC) are removable; the two SUPPORT sheets
  must be kept — the UNIT/SIZE/APPLICATION dropdowns reference ``Units!`` ranges.
"""
from __future__ import annotations

# Absolute default path to the source-of-truth template. NEVER written to; the
# writer opens it read-only and SaveCopyAs's to Downloads.
DEFAULT_TEMPLATE_PATH = (
    r"C:\Users\JohnKim\OneDrive - Oxygen8\Oxygen8 SharePoint Shortcuts"
    r"\Documents - Operations\Production\Coil Checklist Template.xlsx"
)

# Coil category (from the tag prefix) -> the template sheet that models it.
CATEGORY_SHEET = {"DX": "DX", "HGRH": "HGRH", "HWC": "HWC", "CWC": "CWC"}
CATEGORY_SHEETS = ("HWC", "CWC", "DX", "HGRH")  # removable when unused
# Hidden support sheets the dropdowns depend on — NEVER delete these.
SUPPORT_SHEETS_KEEP = ("Install | Drain Pan Width", "Units")

# --- Dropdown vocabularies (data validation) -------------------------------
UNIT_OPTIONS = ("NOVA", "VENTUM H", "VENTUM+", "TERRA H", "TERRA V")

# CoilForge product line/family token -> checklist UNIT value.
UNIT_BY_PRODUCT = {
    "NOVA": "NOVA",
    "VENTUM_H": "VENTUM H",
    "VENTUM H": "VENTUM H",
    "VENTUM_PLUS": "VENTUM+",
    "VENTUM+": "VENTUM+",
    "TERRA H": "TERRA H",
    "TERRA_H": "TERRA H",
    "TERRA H C": "TERRA H",
    "TERRA_H_C": "TERRA H",
    "TERRA V": "TERRA V",
    "TERRA_V": "TERRA V",
}

# Valid SIZE tokens per UNIT (the checklist dropdown lists, Units!A ranges).
SIZE_OPTIONS = {
    "NOVA": ("A16", "A18", "B20", "B22", "C20", "C22", "C24", "C26",
             "C30", "C32", "C40", "C48", "C58", "C70"),
    "TERRA H": (6, 9, 12, 15, 18, 24, 32, 40, 48),
    "TERRA V": ("TV006", "TV009", "TV012", "TV015", "TV018", "TV024", "TV032",
                "TV040", "TV048", "TV060", "TV072", "TV084", "TV100"),
    "VENTUM H": ("H05", "H10", "H15", "H20", "H25", "H30"),
    "VENTUM+": ("V20", "V25", "V30", "V40", "V50", "V60", "V80", "V100",
                "V120", "V150"),
}

# APPLICATION dropdowns. The DX/HGRH/CWC sheets force a single value per UNIT;
# the HWC sheet offers real choices (so an HWC application may need John's input).
APPLICATION_FIXED = {  # used by DX, HGRH, CWC sheets
    "NOVA": "DECOUPLED",
    "TERRA H": "INTEGRATED",
    "TERRA V": "INTEGRATED",
    "VENTUM H": "CPLD EXT",
    "VENTUM+": "INTEGRATED",
}
APPLICATION_HWC_OPTIONS = {
    "NOVA": ("CPLD/DCPLD HORZ", "CPLD/DCPLD VERT", "STANDALONE", "CPLD W/ COOLING"),
    "TERRA H": ("COUPLED", "INTEGRATED"),
    "TERRA V": ("COUPLED", "INTEGRATED"),
    "VENTUM H": ("CPLD/DCPLD STD", "CPLD EXT"),
    "VENTUM+": ("INTEGRATED",),
}

COATING_DEFAULT = "NONE"
COATING_OPTIONS = (
    "NONE", "FINKOTE 2", "FINKOTE 2 W/ UV TOPCOAT", "FINKOTECC", "FINKOTEHP",
    "FINKOTEZX (ZPEX)", "HERESITE", "HERESITE UV", "HERESITE HYDROPHILIC",
    "ELECTROFIN", "ELECTROFIN UV", "BLYGOLD ANIT-CORROSIVE",
    "BLYGOLD ANIT-MICROBIAL", "BLACK POLY COATED FIN",
)
HANDING_OPTIONS = ("LH", "RH")

# --- Checkbox cells (native boolean) we manage, with their default state ----
# Only these are set by the writer; fit checkboxes (WIDTH/HEIGHT/INSTALL FIT) and
# any column-D/E boxes are left exactly as the template has them.
CHECKBOX_DEFAULTS = {
    "COLLARED HOLES": True,    # always on (John)
    "STACKING FLANGES": False,  # always off (John)
    "W/ HGRH": False,          # set True when a same-number HGRH partner exists (DX)
    "HOT GAS BYPASS": False,    # special case only (e.g. ASC)
    "ASC": False,              # DX special case
}

# --- Fillable column-B labels per category sheet ---------------------------
# Canonical "header" block (top of every sheet). Connection-size rows vary by
# category and are listed separately below.
_COMMON_HEADER = (
    "UNIT", "SIZE", "APPLICATION", "COATING", "CASING WIDTH", "CASING HEIGHT",
    "COIL TAG", "QTY", "FH", "FL", "ROWS", "FEEDS/CIRCUITS",
)

# Per-category label sets exactly as they appear in column B (verified 2026-06-30).
SHEET_LABELS = {
    "DX": {
        "header": _COMMON_HEADER,
        "extra_header": ("W/ HGRH", "HOT GAS BYPASS"),  # rows 6-7, before COATING
        "connections": ("SUCTION CONN SZ", "QTY CONN /HEADER"),
        "handing": "HANDING",
        "checkboxes": ("COLLARED HOLES", "STACKING FLANGES"),
        "hgrh_conn": "HGRH CONN SZ",
        "dims": ("CD", "HF", "RF", "TF", "BF", "RB",
                 "O2", "O4", "O6", "O8", "R2", "R4", "R6", "R8",
                 "HD2", "HD4", "HD6", "HD8", "SL2", "SL4", "SL6", "SL8",
                 "S1", "S3", "S5", "S7", "I1", "I3", "I5", "I7",
                 "HD1", "HD3", "HD5", "HD7",
                 "DIST ORIENTATION", "DIST EXTENTION", "ASC", "ASC ORIENTATION",
                 "OAL", "CH"),
    },
    "HGRH": {
        "header": _COMMON_HEADER,
        "connections": ("CONN SZ", "QTY CONN/HEADER"),
        "handing": "HANDING",
        "checkboxes": ("COLLARED HOLES", "STACKING FLANGES"),
        "dims": ("CD", "HF", "RF", "TF", "BF", "RB",
                 "I1", "I3", "I5", "I7", "O2", "O4", "O6", "O8",
                 "R2", "R4", "R6", "R8", "S1", "S3", "S5", "S7",
                 "HD1", "HD2", "HD3", "HD4", "HD5", "HD6", "HD7", "HD8",
                 "SL1", "SL2", "SL3", "SL4", "SL5", "SL6", "SL7", "SL8",
                 "OAL", "CH"),
    },
    "HWC": {
        "header": _COMMON_HEADER,
        "connections": ("IN CONN SZ", "OUT CONN SZ"),
        "handing": "HANDING",
        "checkboxes": ("COLLARED HOLES", "STACKING FLANGES"),
        "dims": ("CD", "HF", "RF", "TF", "BF", "RB", "I/O", "HD", "SL", "OAL", "CH"),
    },
    "CWC": {
        "header": _COMMON_HEADER,
        "connections": ("IN CONN SZ", "OUT CONN SZ"),
        "handing": "HANDING",
        "checkboxes": ("COLLARED HOLES", "STACKING FLANGES"),
        "dims": ("CD", "HF", "RF", "TF", "BF", "RB", "I/O", "HD", "SL", "OAL", "CH"),
    },
}


def normalize_label(label: str) -> str:
    """Collapse whitespace + uppercase so 'QTY CONN /HEADER' and 'QTY CONN/HEADER'
    compare equal when matching a field to its row."""
    return " ".join(str(label).split()).upper()
