from __future__ import annotations

from notes_recovery.core import time_utils


def test_time_utils_invalid_inputs() -> None:
    assert time_utils.mac_absolute_to_datetime("bad") is None
    assert time_utils.unix_to_datetime("bad") is None


def test_time_utils_valid_conversion() -> None:
    ts = time_utils.mac_absolute_to_datetime(0)
    assert ts is not None
    unix = time_utils.unix_to_datetime(0)
    assert unix is not None
