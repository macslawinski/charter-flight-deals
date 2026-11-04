"""Per-source delay override in the polite client."""

from dataclasses import replace

import pytest

from ingest.config import load_settings
from ingest.http_client import delay_range


def test_source_without_override_uses_defaults():
    s = load_settings()
    assert delay_range(s, s.sources["itaka"]) == (s.min_delay_seconds, s.max_delay_seconds)


def test_travelpayouts_has_short_delays():
    s = load_settings()
    lo, hi = delay_range(s, s.sources["travelpayouts"])
    assert 0 < lo <= hi < s.min_delay_seconds


def test_bad_override_is_rejected():
    s = load_settings()
    src = replace(s.sources["itaka"], min_delay_seconds=5.0, max_delay_seconds=1.0)
    with pytest.raises(ValueError, match="bad delay range"):
        delay_range(s, src)
