from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class PipelineEventLogger:
    def __init__(self, *, run_id: uuid.UUID | str, trace_dir: str | Path) -> None:
        self.run_id = str(run_id)
        self.trace_dir = Path(trace_dir)
        self.path = self.trace_dir / f"{self.run_id}.jsonl"
        self._lock = threading.Lock()
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, **payload: Any) -> None:
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "run_id": self.run_id,
            "event_type": event_type,
            **to_jsonable(payload),
        }
        line = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(line + "\n")


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump())
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, (datetime, uuid.UUID, Decimal)):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return value
