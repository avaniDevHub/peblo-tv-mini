"""Loads reference.json (allowed sections/categories/languages, artwork specs).

Kept as a small cached module so both validation and the publish job read the
same source of truth that the challenge shipped.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_REF_PATH = Path(__file__).parent / "reference.json"


@lru_cache
def reference() -> dict:
    return json.loads(_REF_PATH.read_text())


def sections() -> list[str]:
    return reference()["sections"]


def categories() -> list[str]:
    return reference()["categories"]


def languages() -> list[str]:
    return reference()["languages"]


def artwork_specs() -> dict:
    return reference()["artwork_specs"]
