"""Unit tests for deterministic resume redline behavior."""

from __future__ import annotations

import re

import pytest

from backend.redline import redline_diff


DELETE_RE = re.compile(
    r'<span style="color:#c00000"><del>(.*?)</del></span>', re.DOTALL
)
ADD_RE = re.compile(
    r'<span style="color:#008000"><add>(.*?)</add></span>', re.DOTALL
)


def accept_all(redline: str) -> str:
    """Apply every proposed change."""
    return ADD_RE.sub(r"\1", DELETE_RE.sub("", redline))


def reject_all(redline: str) -> str:
    """Reject every proposed change."""
    return ADD_RE.sub("", DELETE_RE.sub(r"\1", redline))


@pytest.mark.parametrize(
    ("baseline", "revised"),
    [
        ("same text", "same text"),
        ("old text", "old short text"),
        ("remove extra word", "remove word"),
        ("replace Python", "replace Java"),
        ("Line one\nLine two", "Line one\nImproved line two"),
        ("Led café growth", "Led café growth by 20%"),
        ("Repeated phrase phrase", "Repeated phrase improved phrase"),
        ("Hello, world!", "Hello world — improved!"),
        ("", "New resume"),
        ("Existing resume", ""),
    ],
)
def test_accept_and_reject_reconstruct_both_versions(
    baseline: str, revised: str
) -> None:
    redline = redline_diff(baseline, revised)

    assert accept_all(redline) == revised
    assert reject_all(redline) == baseline


def test_unchanged_text_has_no_markup() -> None:
    text = "Line one\nLine two"

    assert redline_diff(text, text) == text


def test_redline_never_nests_change_tags() -> None:
    redline = redline_diff("Led product and sales", "Led platform and growth")

    assert "<add><del>" not in redline
    assert "<del><add>" not in redline
