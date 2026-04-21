from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.time_parser import normalize_time_info  # noqa: E402


def test_year_granularity() -> None:
    info = normalize_time_info("2026年", context_text="计划在2026年推进", today=date(2026, 4, 21))
    assert info is not None
    assert info.granularity == "year"
    assert info.normalized_value == "2026"


def test_year_month_granularity() -> None:
    info = normalize_time_info("2026年5月", context_text="计划在2026年5月完成", today=date(2026, 4, 21))
    assert info is not None
    assert info.granularity == "month"
    assert info.normalized_value == "2026-05"


def test_vague_time_stays_uncertain() -> None:
    info = normalize_time_info("尽快", context_text="王敏来跟，尽快同步", today=date(2026, 4, 21))
    assert info is not None
    assert info.is_uncertain is True
    assert info.normalized_value is None


def test_week_range_stays_uncertain() -> None:
    info = normalize_time_info("下周左右", context_text="上线时间大概下周左右", today=date(2026, 4, 21))
    assert info is not None
    assert info.is_uncertain is True
    assert info.granularity in {"range", "unknown"}
