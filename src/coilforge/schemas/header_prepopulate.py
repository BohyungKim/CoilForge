"""Pydantic v2 models for the deterministic header prepopulation engine.

Scope is strictly header prepopulation. See
``docs/rules/coil_header_rule_extraction.md`` for the source-of-truth rule
citations and ``docs/codex_implementation_prompt.md`` for the contract.

Confidence/review gate (enforced in the engine, asserted by the test suite):

* ``HIGH``     -> field appears in ``HeaderPrepopulateResponse.values``.
* ``MEDIUM``   -> field appears ONLY in ``suggestions`` with ``review_required``.
* ``LOW`` / ``CONFLICT`` -> field appears ONLY in ``blocked`` with a
  ``blocked_reason`` and ``value=None``.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CoilType(str, Enum):
    """Type of coil (CHK sheet / EZ Coil coil family)."""

    DX = "DX"
    HGRH = "HGRH"
    CWC = "CWC"
    HWC = "HWC"


class ProductFamily(str, Enum):
    """Product platform. ``TERRA`` is intentionally coarse; the SOP Rev I

    distinguishes Terra H / Terra H C / Terra V and W-Ctrl vs D-Ctrl, which is
    why Terra-variant-dependent rules are gated behind ``terra_variant``.

    Terra split (phased, John 2026-07-14): ``TERRA_H`` and ``TERRA_V`` are the
    first-class target families. Phase 1 accepts them as valid ``product_type``
    inputs and normalizes them onto ``TERRA`` + ``terra_variant`` at the engine
    entry (``prepopulate``), so every ``[TERRA]``-scoped rule and ``terra_variant``
    branch keeps working unchanged. Later phases relink rules to key on
    ``TERRA_H`` / ``TERRA_V`` natively and retire the coarse ``TERRA``.
    """

    NOVA = "NOVA"
    TERRA = "TERRA"
    TERRA_H = "TERRA_H"
    TERRA_V = "TERRA_V"
    VENTUM_H = "VENTUM_H"
    VENTUM_PLUS = "VENTUM_PLUS"
    # Omnia (OW### model codes, John 2026-08-25): a first-class family that inherits
    # EVERY Ventum+ rule and the dedicated Ventum+ template set; its only own rule is
    # R-011o (TF = BF = 0.625, vs Ventum+ 1.0). Python branches that special-case
    # Ventum+ must test ``in VENTUM_PLUS_CLASS`` so Omnia cannot silently fall out.
    OMNIA = "OMNIA"


# Families that share the Ventum+ engine branches (R-052 flat R, HGRH CD = 3*conn,
# R-063b water SL, install_width drain-pan compare, dedicated Ventum+ templates).
VENTUM_PLUS_CLASS: frozenset[ProductFamily] = frozenset(
    {ProductFamily.VENTUM_PLUS, ProductFamily.OMNIA}
)
VENTUM_PLUS_CLASS_VALUES: frozenset[str] = frozenset(p.value for p in VENTUM_PLUS_CLASS)


class TerraVariant(str, Enum):
    TERRA_H = "TERRA_H"
    TERRA_H_C = "TERRA_H_C"
    TERRA_V = "TERRA_V"


class TerraCtrlType(str, Enum):
    W_CTRL = "W_CTRL"
    D_CTRL = "D_CTRL"


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    CONFLICT = "CONFLICT"


class SizeClass(str, Enum):
    NOVA_1IN = "NOVA_1IN"
    NOVA_2IN = "NOVA_2IN"
    NA = "N/A"


class HeaderPrepopulateRequest(BaseModel):
    """Engine input.

    Only ``type_of_coil``, ``product_type`` and ``unit_size`` are required;
    every extended input from extraction-doc section 4 is optional and defaults
    to ``None`` so the constant layer is always servable from the three core
    inputs.
    """

    model_config = ConfigDict(extra="forbid")

    type_of_coil: CoilType
    product_type: ProductFamily
    unit_size: str

    # --- Extended inputs (extraction doc section 4). All optional. ---
    terra_variant: TerraVariant | None = None
    terra_ctrl_type: TerraCtrlType | None = None
    application: str | None = None
    rows: int | None = None
    feeds: int | None = None
    header_count: int | None = None  # drawing header count (1HD-4HD); drives R-090
    qty_conn_per_header: int | None = None
    circuits: int | None = None
    suction_conn_size: float | None = None
    conn_size: float | None = None
    handing: str | None = None
    coating: str | None = None
    with_hgrh: bool | None = None
    hgrh_conn_size: float | None = None
    hot_gas_bypass: bool | None = None
    installed_on_drain_pan: bool | None = None
    fh: float | None = None
    fl: float | None = None
    back_to_back: bool | None = None
    qty_valves: int | None = None


class FieldResult(BaseModel):
    """Per-field prepopulation outcome with full traceability."""

    model_config = ConfigDict(extra="forbid")

    value: Any = None
    confidence: Confidence
    evidence_refs: list[str] = Field(default_factory=list)
    review_required: bool = False
    review_required_reason: str | None = None
    missing_inputs: list[str] = Field(default_factory=list)
    blocked_reason: str | None = None
    # Provenance (1c): the primary rule id that produced this result. Captured into the
    # rule_firing ledger; NEVER part of the drawing/engine payload. exclude=True keeps
    # every serialization byte-identical, and default=None keeps the unmerged phase5
    # worktree's rule_id-less constructors merge-compatible (additive-only, on the model too).
    rule_id: str | None = Field(default=None, exclude=True)


class HeaderPrepopulateResponse(BaseModel):
    """Engine output, partitioned by the confidence/review gate."""

    model_config = ConfigDict(extra="forbid")

    values: dict[str, FieldResult] = Field(default_factory=dict)
    suggestions: dict[str, FieldResult] = Field(default_factory=dict)
    blocked: dict[str, FieldResult] = Field(default_factory=dict)
    missing_inputs: list[str] = Field(default_factory=list)
    review_required: bool = False
    blocked_reason: str | None = None
