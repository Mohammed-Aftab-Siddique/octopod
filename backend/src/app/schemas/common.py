from datetime import UTC, datetime
from typing import Annotated

from pydantic import BeforeValidator


def _as_utc(value: object) -> object:
    """SQLite returns naive datetimes even for timezone-aware columns."""
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


UTCDateTime = Annotated[datetime, BeforeValidator(_as_utc)]
