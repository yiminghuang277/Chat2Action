from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta

from backend.app.models.schemas import CertaintyLevel, StructuredTimeInfo, TimeGranularity, TimeRelation


YEAR_PATTERN = re.compile(r"(?P<year>\d{4})年")
YEAR_MONTH_PATTERN = re.compile(r"(?P<year>\d{4})年(?P<month>\d{1,2})月")
ABSOLUTE_DATE_PATTERN = re.compile(
    r"(?:(?P<year>\d{4})[/-])?(?P<month>\d{1,2})[/-](?P<day>\d{1,2})(?:\s*(?P<hour>\d{1,2})(?::(?P<minute>\d{1,2}))?)?"
)
WEEKDAY_PATTERN = re.compile(r"(?P<prefix>下周|本周|这周)?周(?P<weekday>[一二三四五六日天])")

WEEKDAY_MAP = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
}

TIME_OF_DAY_DEFAULTS = {
    "上午": (10, 0),
    "中午": (12, 0),
    "下午": (15, 0),
    "晚上": (20, 0),
    "下班前": (18, 0),
    "中午前": (12, 0),
}

UNCERTAIN_MARKERS = ("尽快", "近期", "左右", "大概", "约", "再定", "待定")
DEADLINE_MARKERS = ("截止", "最晚", "前", "之前", "以内", "内")
SYNC_MARKERS = ("同步", "回复", "反馈")
START_MARKERS = ("开始", "启动", "着手", "开工")


def _combine(target_date: date, hour: int = 18, minute: int = 0) -> str:
    return datetime.combine(target_date, time(hour=hour, minute=minute)).strftime("%Y-%m-%d %H:%M")


def _month_bounds(target_year: int, target_month: int) -> tuple[str, str]:
    last_day = calendar.monthrange(target_year, target_month)[1]
    start = datetime(target_year, target_month, 1, 0, 0).strftime("%Y-%m-%d %H:%M")
    end = datetime(target_year, target_month, last_day, 23, 59).strftime("%Y-%m-%d %H:%M")
    return start, end


def _year_bounds(target_year: int) -> tuple[str, str]:
    return (
        datetime(target_year, 1, 1, 0, 0).strftime("%Y-%m-%d %H:%M"),
        datetime(target_year, 12, 31, 23, 59).strftime("%Y-%m-%d %H:%M"),
    )


def _relation_from_text(context_text: str, raw_text: str | None = None) -> TimeRelation:
    combined = f"{context_text} {raw_text or ''}"
    if any(marker in combined for marker in SYNC_MARKERS):
        return TimeRelation.sync_time
    if any(marker in combined for marker in START_MARKERS):
        return TimeRelation.start_time
    if any(marker in combined for marker in DEADLINE_MARKERS):
        return TimeRelation.deadline
    return TimeRelation.unknown


def _certainty_from_info(is_uncertain: bool, normalized_value: str | None) -> CertaintyLevel:
    if is_uncertain and normalized_value is None:
        return CertaintyLevel.low
    if is_uncertain:
        return CertaintyLevel.medium
    return CertaintyLevel.high if normalized_value else CertaintyLevel.medium


def normalize_time_info(
    raw_text: str | None,
    context_text: str = "",
    today: date | None = None,
    relation: TimeRelation | str | None = None,
) -> StructuredTimeInfo | None:
    today = today or date.today()
    if not raw_text:
        return None

    text = raw_text.strip()
    if not text:
        return None

    info = StructuredTimeInfo(raw_text=text)
    info.relation = relation if isinstance(relation, TimeRelation) else _relation_from_text(context_text, text)
    info.is_uncertain = any(marker in text for marker in UNCERTAIN_MARKERS)

    year_month_match = YEAR_MONTH_PATTERN.search(text)
    if year_month_match:
        year = int(year_month_match.group("year"))
        month = int(year_month_match.group("month"))
        start, end = _month_bounds(year, month)
        info.normalized_value = f"{year:04d}-{month:02d}"
        info.range_start = start
        info.range_end = end
        info.granularity = TimeGranularity.month
        info.certainty_level = _certainty_from_info(info.is_uncertain, info.normalized_value)
        return info

    year_match = YEAR_PATTERN.search(text)
    if year_match:
        year = int(year_match.group("year"))
        start, end = _year_bounds(year)
        info.normalized_value = str(year)
        info.range_start = start
        info.range_end = end
        info.granularity = TimeGranularity.year
        info.certainty_level = _certainty_from_info(info.is_uncertain, info.normalized_value)
        return info

    absolute_match = ABSOLUTE_DATE_PATTERN.search(text)
    if absolute_match:
        year = int(absolute_match.group("year") or today.year)
        month = int(absolute_match.group("month"))
        day = int(absolute_match.group("day"))
        hour = int(absolute_match.group("hour") or 18)
        minute = int(absolute_match.group("minute") or 0)
        normalized = datetime(year, month, day, hour, minute).strftime("%Y-%m-%d %H:%M")
        info.normalized_value = normalized
        info.range_start = normalized
        info.range_end = normalized
        info.granularity = TimeGranularity.hour if absolute_match.group("hour") else TimeGranularity.day
        info.certainty_level = _certainty_from_info(info.is_uncertain, info.normalized_value)
        return info

    if "月底" in text:
        last_day = calendar.monthrange(today.year, today.month)[1]
        end = _combine(date(today.year, today.month, last_day), 18, 0)
        info.normalized_value = end if "前" in text else None
        info.range_start = _combine(today, 0, 0)
        info.range_end = end
        info.granularity = TimeGranularity.range
        info.is_uncertain = True
        info.certainty_level = _certainty_from_info(info.is_uncertain, info.normalized_value)
        return info

    weekday_match = WEEKDAY_PATTERN.search(text)
    if weekday_match:
        weekday = WEEKDAY_MAP[weekday_match.group("weekday")]
        prefix = weekday_match.group("prefix")
        delta = (weekday - today.weekday()) % 7
        if prefix == "下周":
            delta = delta + 7 if delta != 0 else 7
        elif delta == 0:
            delta = 7
        target = today + timedelta(days=delta)
        hour, minute = 18, 0
        for marker, default_time in TIME_OF_DAY_DEFAULTS.items():
            if marker in text:
                hour, minute = default_time
                break
        normalized = _combine(target, hour, minute)
        info.normalized_value = normalized
        info.range_start = _combine(target, 0, 0)
        info.range_end = normalized
        info.granularity = TimeGranularity.day
        info.is_uncertain = info.is_uncertain or ("左右" in text)
        info.certainty_level = _certainty_from_info(info.is_uncertain, info.normalized_value)
        return info

    for label, offset in (("后天", 2), ("明天", 1), ("今天", 0)):
        if label in text:
            hour, minute = 18, 0
            for marker, default_time in TIME_OF_DAY_DEFAULTS.items():
                if marker in text:
                    hour, minute = default_time
                    break
            target = today + timedelta(days=offset)
            normalized = _combine(target, hour, minute)
            info.normalized_value = normalized
            info.range_start = _combine(target, 0, 0)
            info.range_end = normalized
            info.granularity = TimeGranularity.day
            info.certainty_level = _certainty_from_info(info.is_uncertain, info.normalized_value)
            return info

    if any(marker in text for marker in ("下周", "本周", "这周")):
        start = today
        if "下周" in text:
            start = today + timedelta(days=(7 - today.weekday()))
        end = start + timedelta(days=6)
        info.range_start = _combine(start, 0, 0)
        info.range_end = _combine(end, 23, 59)
        info.normalized_value = None
        info.granularity = TimeGranularity.range
        info.is_uncertain = True
        info.certainty_level = _certainty_from_info(info.is_uncertain, info.normalized_value)
        return info

    if any(marker in text for marker in UNCERTAIN_MARKERS):
        info.granularity = TimeGranularity.unknown
        info.certainty_level = _certainty_from_info(True, None)
        return info

    info.granularity = TimeGranularity.unknown
    info.certainty_level = _certainty_from_info(info.is_uncertain, info.normalized_value)
    return info
