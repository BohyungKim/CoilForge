from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coilforge.submittal.pdf_intake import (
    _normalize_header_wall_schedule,
    header_wall_schedule_confidence,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", "(L)"),
        ("   ", "(L)"),
        ("L", "(L)"),
        ("Type L", "(L)"),
        ("type l", "(L)"),
        ("Copper Type L", "(L)"),
        ("(L)", "(L)"),
        ("K", "(K)"),
        ("Type K", "(K)"),
        ("Copper Type K", "(K)"),
        ("Heavy Wall", "(K)"),
        ("heavy   wall", "(K)"),
        ("(K)", "(K)"),
    ],
)
def test_normalize_known_terms(value: str, expected: str) -> None:
    assert _normalize_header_wall_schedule(value) == expected


@pytest.mark.parametrize("value", ["Type M", "Schedule 40", "garbage", "LK"])
def test_normalize_unknown_returns_none(value: str) -> None:
    # Unknown values return None so the intake layer blocks rather than guesses.
    assert _normalize_header_wall_schedule(value) is None


def test_normalize_none_defaults_to_l() -> None:
    assert _normalize_header_wall_schedule(None) == "(L)"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", "inferred"),
        ("   ", "inferred"),
        (None, "inferred"),
        ("Type L", "confirmed"),
        ("(K)", "confirmed"),
        ("Heavy Wall", "confirmed"),
        ("Type M", "ambiguous"),
        ("garbage", "ambiguous"),
    ],
)
def test_confidence_tiers(value: str | None, expected: str) -> None:
    assert header_wall_schedule_confidence(value) == expected
