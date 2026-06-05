from coilforge.phase2a.app import app
from coilforge.phase2a.fixtures import load_default_dx_header1_fixture
from coilforge.phase2a.renderer import DEFAULT_VIEWBOX, REVIEW_WATERMARK


def load_default_state():
    """Compatibility wrapper for the earlier Phase 2A web shell entrypoint."""
    return load_default_dx_header1_fixture()


__all__ = ["DEFAULT_VIEWBOX", "REVIEW_WATERMARK", "app", "load_default_state"]
