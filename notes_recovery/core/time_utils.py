from __future__ import annotations

import datetime
from typing import Optional


def mac_absolute_to_datetime(value: Optional[float]) -> Optional[datetime.datetime]:
    if value is None:
        return None
    try:
        seconds = float(value)
    except Exception:
        return None
    base = datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc)
    try:
        return base + datetime.timedelta(seconds=seconds)
    except Exception:
        return None


def unix_to_datetime(value: Optional[float]) -> Optional[datetime.datetime]:
    if value is None:
        return None
    try:
        return datetime.datetime.fromtimestamp(float(value), tz=datetime.timezone.utc)
    except Exception:
        return None
