# time_utils.py
import datetime
import math
from functools import lru_cache
from typing import Optional

import pandas as pd

from config_context import CONFIG

_UTC_TZ = datetime.timezone.utc
_LOCAL_TZ = CONFIG.TIMEZONE


@lru_cache(maxsize=4096)
def ms_to_datetime(ms: Optional[int]) -> Optional[datetime.datetime]:
    """Convert millisecond timestamp to local datetime (cached)."""
    if not ms:
        return None
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000, tz=_UTC_TZ).astimezone(_LOCAL_TZ)
    except (ValueError, OSError):
        return None


def datetime_to_epoch(dt_like) -> Optional[int]:
    """Convert datetime-like object to epoch milliseconds."""
    if dt_like is None or (isinstance(dt_like, float) and math.isnan(dt_like)):
        return None

    if isinstance(dt_like, int):
        return dt_like

    try:
        if not isinstance(dt_like, (datetime.datetime, pd.Timestamp)):
            dt = pd.to_datetime(dt_like)
        else:
            dt = dt_like

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_LOCAL_TZ)

        if isinstance(dt, pd.Timestamp):
            return int(dt.tz_convert(_UTC_TZ).value // 1_000_000)
        else:
            return int(dt.astimezone(_UTC_TZ).timestamp() * 1000)
    except Exception:
        return None


@lru_cache(maxsize=1024)
def get_fiscal_year_cached(timestamp: int) -> str:
    dt = datetime.datetime.fromtimestamp(timestamp / 1000, tz=_LOCAL_TZ)
    year_offset = 1 if dt.month >= 10 else 0
    return f"FY{(dt.year % 100) + year_offset}"


def get_fiscal_year(dt=None) -> str:
    if not dt:
        return get_fiscal_year_cached(int(datetime.datetime.now().timestamp() * 1000))

    if not isinstance(dt, (datetime.datetime, pd.Timestamp)):
        dt = pd.to_datetime(dt)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_LOCAL_TZ)
    elif dt.tzinfo != _LOCAL_TZ:
        dt = dt.astimezone(_LOCAL_TZ)

    year_offset = 1 if dt.month >= 10 else 0
    return f"FY{(dt.year % 100) + year_offset}"


def month_floor(dt=None) -> datetime.datetime:
    if not dt:
        dt = datetime.datetime.now(_LOCAL_TZ)
    elif not isinstance(dt, (datetime.datetime, pd.Timestamp)):
        dt = pd.to_datetime(dt)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_LOCAL_TZ)
    elif dt.tzinfo != _LOCAL_TZ:
        dt = dt.astimezone(_LOCAL_TZ)

    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
