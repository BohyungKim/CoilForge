from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any


VOLATILE_METADATA_KEYS = {
    "created_at",
    "generated_at",
    "timestamp",
    "updated_at",
}

ISO_TIMESTAMP_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ][0-2]\d:[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def normalize_svg_for_regression(svg: str) -> str:
    """Return a stable, text-preserving SVG representation for regression tests."""

    if not svg.strip():
        return ""

    root = ET.fromstring(svg)
    return "\n".join(_normalize_element(root))


def normalize_svg_metadata_for_regression(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _normalize_metadata_value(key, value)
        for key, value in sorted(metadata.items(), key=lambda item: item[0])
    }


def _normalize_element(element: ET.Element, depth: int = 0) -> list[str]:
    indent = "  " * depth
    tag = _local_name(element.tag)
    attrs = " ".join(
        f'{_local_name(key)}="{_normalize_text_value(value)}"'
        for key, value in sorted(element.attrib.items(), key=lambda item: _local_name(item[0]))
    )
    start = f"{indent}<{tag}{(' ' + attrs) if attrs else ''}>"
    text = _normalize_text_value(element.text or "")
    children: list[str] = []
    for child in list(element):
        children.extend(_normalize_element(child, depth + 1))

    if not children:
        if text:
            return [f"{start}{text}</{tag}>"]
        return [f"{start}</{tag}>"]

    lines = [start]
    if text:
        lines.append(f"{indent}  {text}")
    lines.extend(children)
    lines.append(f"{indent}</{tag}>")
    return lines


def _normalize_metadata_value(key: str, value: Any) -> Any:
    if key in VOLATILE_METADATA_KEYS:
        return "<TIMESTAMP>"
    if isinstance(value, str):
        return _normalize_text_value(value)
    if isinstance(value, list):
        return [_normalize_metadata_value("", item) for item in value]
    if isinstance(value, dict):
        return {
            child_key: _normalize_metadata_value(child_key, child_value)
            for child_key, child_value in sorted(value.items(), key=lambda item: item[0])
        }
    return value


def _normalize_text_value(value: str) -> str:
    normalized = " ".join(str(value).split())
    normalized = ISO_TIMESTAMP_PATTERN.sub("<TIMESTAMP>", normalized)
    return UUID_PATTERN.sub("<UUID>", normalized)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag
