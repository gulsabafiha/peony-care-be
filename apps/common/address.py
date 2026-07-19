from __future__ import annotations

import re

_ROAD_SUFFIX = re.compile(
    r"\s+(Rd|Road|St|Street|Ave|Avenue|Dr|Drive|Blvd|Lane|Ln|"
    r"Cres|Crescent|Ter|Terrace|Way|Close|Walk)\.?$",
    re.IGNORECASE,
)
_LEADING_NUMBER = re.compile(r"^\d+[A-Za-z]?\s+")


def derive_area_label(address: str | None) -> str | None:
    """Best-effort neighbourhood from a Singapore-style street address."""
    if not address or not address.strip():
        return None
    first = address.split(",")[0].strip()
    first = _LEADING_NUMBER.sub("", first)
    first = _ROAD_SUFFIX.sub("", first).strip()
    return first or None
