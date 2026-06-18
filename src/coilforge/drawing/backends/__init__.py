"""Renderer backends for the parametric drawing engine.

Each backend consumes the same inch-based layout (Layer 2) and decides how to present
it. SVG (review aid) lives here today; DXF (1:1 shop geometry) and PDF (submittal at a
declared scale) slot in later without touching the model or layout layers.
"""
