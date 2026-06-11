"""Template-first drawing population helpers."""

from coilforge.template_population.catalog import (
    TEMPLATE_BUCKET_COUNT,
    DrawingTemplateCatalog,
    DrawingTemplateEntry,
    TemplateSelectionRequest,
    TemplateSelectionResult,
    get_template_entry,
    list_template_entries,
    load_drawing_template_catalog,
    select_drawing_template,
)
from coilforge.template_population.slot_population import (
    SlotPopulationResult,
    populate_template_slots,
)

__all__ = [
    "TEMPLATE_BUCKET_COUNT",
    "DrawingTemplateCatalog",
    "DrawingTemplateEntry",
    "SlotPopulationResult",
    "TemplateSelectionRequest",
    "TemplateSelectionResult",
    "get_template_entry",
    "list_template_entries",
    "load_drawing_template_catalog",
    "populate_template_slots",
    "select_drawing_template",
]
