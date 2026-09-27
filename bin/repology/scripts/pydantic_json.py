"""Stand-in for pydantic.json: json.dumps default for repository records."""

import dataclasses
import datetime
import enum


def pydantic_encoder(obj):
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)

    if isinstance(obj, enum.Enum):
        return obj.value

    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()

    if isinstance(obj, datetime.timedelta):
        return obj.total_seconds()

    raise TypeError(f'cannot encode {type(obj).__name__}')
