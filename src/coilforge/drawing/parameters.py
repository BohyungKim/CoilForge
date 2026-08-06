from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from coilforge.contracts.evidence import SourceEvidence
from coilforge.direct_coil.draft import DirectCoilDraftField, DirectCoilInputDraft
from coilforge.interfaces.direct_coil import DIRECT_COIL_FIELD_REGISTRY


DRAWING_PARAMETER_KEYS: tuple[str, ...] = tuple(
    field_key
    for field_key, definition in DIRECT_COIL_FIELD_REGISTRY.items()
    if definition.group == "Drawing Parameters"
)
REQUIRED_PREVIEW_PARAMETER_KEYS: tuple[str, ...] = tuple(
    field_key
    for field_key in DRAWING_PARAMETER_KEYS
    if DIRECT_COIL_FIELD_REGISTRY[field_key].required
)

DrawingParameterMode = Literal["auto", "manual", "default", "blocked", "unmapped"]
DrawingParameterStatus = Literal["ready", "review_required", "blocked", "unmapped"]


class PreviewDefaultValue(BaseModel):
    """Explicit sanitized fixture/default value for preview-only use."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: Any
    unit: str = "in"
    source: Literal[
        "sanitized_fixture/default", "rule_engine/generated", "ez_json/as_built"
    ] = "sanitized_fixture/default"
    reason: str = "sanitized default preview value"

    @field_validator("key", "unit", "reason", mode="before")
    @classmethod
    def normalize_strings(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()


class DrawingParameterOverride(BaseModel):
    """Manual preview value that remains review-required unless separately approved."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: Any
    unit: str = "in"
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    override_reason: str
    reviewed_by: str | None = None
    review_status: str = "unreviewed"

    @field_validator("key", "unit", "override_reason", "reviewed_by", "review_status", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value).strip()


class DrawingParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    value: Any = None
    unit: str | None = None
    mode: DrawingParameterMode
    source_evidence: list[SourceEvidence] = Field(default_factory=list)
    status: DrawingParameterStatus
    review_required: bool
    blocked_reason: str | None = None
    manual_override: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slot(self) -> str | None:
        """The engine slot this row renders (``"slot.S1"`` for ``S``, ``"slot.O4"`` for ``O2``).

        COMPUTED rather than passed in, deliberately. ``DrawingParameter`` is built at
        twelve call sites across three modules; a constructor argument would be forgotten
        at one of them and that row would silently lose its identity. It is a pure
        function of ``key``, so the model can answer it and no caller can get it wrong.

        Why it is on the wire at all: the Coil Checklist comparison already reports each
        dimension by slot id, but the panel's key and the checklist's label disagree about
        what the SAME dimension is called (the panel's logical ``O2`` is the sheet's ``O4``,
        while the sheet's own ``O2`` is the panel's ``O``). Joining the two by name would
        put the mismatch flag on the wrong row. The slot is the only shared identity, and
        re-deriving the logical<->parity bridge in JavaScript would make a third copy of a
        mapping the code says must live in exactly one place. ``None`` for ``ZD``/``ZD2``,
        which have no slot.
        """
        from coilforge.services.drawing_param_resolver import slot_for_param_key

        return slot_for_param_key(self.key)


class DrawingParameterSet(BaseModel):
    """Preview-only drawing parameter set. Export is intentionally disabled."""

    model_config = ConfigDict(extra="forbid")

    parameters: dict[str, DrawingParameter]
    preview_allowed: bool
    export_allowed: bool = False
    blocked_parameters: list[str] = Field(default_factory=list)
    review_required_parameters: list[str] = Field(default_factory=list)
    required_preview_parameters: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def resolve_drawing_parameters(
    draft: DirectCoilInputDraft,
    *,
    manual_overrides: list[DrawingParameterOverride | dict[str, Any]] | None = None,
    default_preview_values: list[PreviewDefaultValue | dict[str, Any]] | None = None,
) -> DrawingParameterSet:
    overrides_by_key = {
        override.key: override
        for override in (
            DrawingParameterOverride.model_validate(item)
            for item in (manual_overrides or [])
        )
    }
    defaults_by_key = {
        default.key: default
        for default in (
            PreviewDefaultValue.model_validate(item)
            for item in (default_preview_values or [])
        )
    }

    parameters = {
        key: _resolve_one_parameter(
            key,
            draft.fields.get(key),
            overrides_by_key.get(key),
            defaults_by_key.get(key),
        )
        for key in DRAWING_PARAMETER_KEYS
    }
    blocked_parameters = [
        key for key, parameter in parameters.items() if parameter.status == "blocked"
    ]
    review_required_parameters = [
        key for key, parameter in parameters.items() if parameter.review_required
    ]
    missing_required_preview = [
        key
        for key in REQUIRED_PREVIEW_PARAMETER_KEYS
        if parameters[key].value in (None, "") or parameters[key].status == "blocked"
    ]
    preview_allowed = not missing_required_preview

    return DrawingParameterSet(
        parameters=parameters,
        preview_allowed=preview_allowed,
        export_allowed=False,
        blocked_parameters=blocked_parameters,
        review_required_parameters=review_required_parameters,
        required_preview_parameters=list(REQUIRED_PREVIEW_PARAMETER_KEYS),
        notes=[
            "Preview parameters are review aids only.",
            "export_allowed remains false until John approves drawing semantics and export policy.",
            "No engineering formulas are applied by this resolver.",
        ],
    )


def _resolve_one_parameter(
    key: str,
    draft_field: DirectCoilDraftField | None,
    override: DrawingParameterOverride | None,
    default: PreviewDefaultValue | None,
) -> DrawingParameter:
    definition = DIRECT_COIL_FIELD_REGISTRY[key]
    if override is not None:
        return DrawingParameter(
            key=key,
            label=definition.label,
            value=override.value,
            unit=override.unit,
            mode="manual",
            source_evidence=list(override.source_evidence),
            status="review_required",
            review_required=True,
            blocked_reason=None,
            manual_override=True,
        )

    if draft_field is not None and draft_field.value not in (None, ""):
        status = "review_required" if draft_field.status == "ready" else draft_field.status
        if status == "manual_override":
            status = "review_required"
        return DrawingParameter(
            key=key,
            label=draft_field.label,
            value=draft_field.value,
            unit=draft_field.unit,
            mode="auto",
            source_evidence=list(draft_field.source_evidence),
            status=status,
            review_required=True if status == "review_required" else draft_field.review_required,
            blocked_reason=draft_field.blocked_reason,
            manual_override=draft_field.manual_override,
        )

    if default is not None:
        evidence = SourceEvidence(
            evidence_id=f"EV-DRAWING-DEFAULT-{key}",
            source_type=default.source,
            source_id="SANITIZED-DRAWING-PREVIEW-DEFAULTS",
            source_location=f"sanitized-default:{key}",
            source_key=key,
            source_value=default.value,
            normalized_value=default.value,
            unit=default.unit,
            confidence="inferred",
            review_status="unreviewed",
            evidence_status="candidate",
            notes=[default.reason],
        )
        return DrawingParameter(
            key=key,
            label=definition.label,
            value=default.value,
            unit=default.unit,
            mode="default",
            source_evidence=[evidence],
            status="review_required",
            review_required=True,
            blocked_reason=None,
            manual_override=False,
        )

    status = "blocked" if definition.required else "unmapped"
    return DrawingParameter(
        key=key,
        label=definition.label,
        value=None,
        unit=definition.unit,
        mode="blocked" if definition.required else "unmapped",
        source_evidence=[],
        status=status,
        review_required=definition.required,
        blocked_reason="required preview parameter missing" if definition.required else None,
        manual_override=False,
    )
